"""LangGraph wiring: planner → tool_executor → reflect → (loop | finalize) → END.

Why an explicit graph instead of a black-box agent executor? Because the whole
selling point is a *visible* control flow with real branches: the planner's choice,
the reflection retry, and the forced stop on ``max_iterations`` are all edges you can
point at in a trace — not hidden inside a framework's while-loop.

The LLM provider is injected (``build_graph(llm=...)``) so tests/CI can run the entire
machine — including the reflection loop — with the deterministic mock provider.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .llm import FINAL_TOOL, LLMProvider, get_llm
from .planner import plan
from .reflect import reflect
from .schemas import FinalAnswer, PlannerDecision
from .state import AgentState, ToolCall
from .tools import run_tool

# --------------------------------------------------------------------------- #
# finalize node (structured output)
# --------------------------------------------------------------------------- #
FINALIZE_SYSTEM = """You are the answer writer of a financial-research agent. Using ONLY
the information gathered by the tools below, write the final answer to the user's
question.

Requirements:
- Put every derived or reported numeric value into `key_numbers` with a descriptive key
  (e.g. "aapl_revenue_q3_2025_usd": 94036000000, "gross_margin_pct": 46.2).
- Cite each source you actually used in `citations` (SEC filing + concept, a URL, or the
  indexed filing passages).
- Set `confidence` honestly: use "low" if required data was missing or a tool errored,
  "high" only when the question is fully and cleanly answered from solid sources.
- Do not invent numbers that are not present in the gathered data.
"""

FINAL_TOOL_SCHEMA = {
    "name": FINAL_TOOL,
    "description": "Emit the final structured answer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string", "description": "the natural-language answer"},
            "key_numbers": {
                "type": "object",
                "additionalProperties": {"type": "number"},
                "description": "named numeric results",
            },
            "citations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "detail": {"type": "string"},
                    },
                    "required": ["source", "detail"],
                },
            },
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "caveats": {"type": "string"},
        },
        "required": ["answer", "confidence"],
    },
}


def _finalize_user(state: AgentState) -> str:
    lines = [f"USER QUESTION:\n{state.query}\n", "GATHERED INFORMATION:"]
    if not state.tool_calls:
        lines.append("(no tools were called)")
    for tc in state.tool_calls:
        status = "ok" if tc.ok else "ERROR"
        lines.append(f"- [{status}] {tc.tool}({tc.input}) -> {tc.output}")
    if state.reflection_notes:
        lines.append("\nReflection notes raised during the run:")
        lines.extend(f"- {n}" for n in state.reflection_notes)
    lines.append("\nWrite the final structured answer now.")
    return "\n".join(lines)


def _coerce_final(raw: dict) -> dict:
    """Best-effort repair of a slightly malformed structured answer.

    Models occasionally hand back ``citations`` / ``key_numbers`` as a JSON *string*
    (sometimes with stray tool-call markup). Rather than fail the whole run, we coerce
    them back into the right shape.
    """
    out = dict(raw)
    for field, empty in (("citations", []), ("key_numbers", {})):
        val = out.get(field)
        if isinstance(val, str):
            try:
                val = json.loads(val[val.index("[") if empty == [] else val.index("{"):])
            except Exception:
                val = empty
            out[field] = val
    if not isinstance(out.get("citations"), list):
        out["citations"] = []
    if not isinstance(out.get("key_numbers"), dict):
        out["key_numbers"] = {}
    return out


def build_final_answer(state: AgentState, llm: LLMProvider) -> FinalAnswer:
    raw = llm.complete_json(
        system=FINALIZE_SYSTEM,
        user=_finalize_user(state),
        tool=FINAL_TOOL_SCHEMA,
        context={"state": state},
    )
    try:
        answer = FinalAnswer.model_validate(raw)
    except Exception:
        try:
            answer = FinalAnswer.model_validate(_coerce_final(raw))
        except Exception as exc:  # last resort: keep the prose, drop the rest
            answer = FinalAnswer(
                answer=str(raw.get("answer", "(unstructured answer)"))[:2000],
                key_numbers={},
                citations=[],
                confidence="low",
                caveats=f"Structured-output repair failed ({type(exc).__name__}).",
            )

    # Real confidence logic — not always "high".
    reasons = []
    if state.forced_finish:
        reasons.append("the reasoning loop hit its iteration cap")
    if state.had_tool_error:
        reasons.append("at least one tool call failed")
    if reasons:
        note = "Answer may be incomplete because " + " and ".join(reasons) + "."
        answer = answer.model_copy(
            update={
                "confidence": "low",
                "caveats": f"{answer.caveats + ' ' if answer.caveats else ''}{note}",
            }
        )
    return answer


# --------------------------------------------------------------------------- #
# graph construction
# --------------------------------------------------------------------------- #
def build_graph(llm: LLMProvider | None = None, checkpointer: Any | None = None):
    """Compile and return the FinAgent state machine."""
    llm = llm or get_llm()

    def planner_node(state: AgentState) -> dict:
        # Hard stop: if we've looped enough, force a finish without spending an LLM call.
        if state.iteration >= state.max_iterations:
            return {
                "pending": PlannerDecision(
                    action="finish",
                    reasoning=f"Reached max_iterations ({state.max_iterations}); finishing.",
                ),
                "forced_finish": True,
            }
        decision = plan(state, llm)
        return {"pending": decision, "plan": decision.reasoning}

    def tool_executor_node(state: AgentState) -> dict:
        dec = state.pending
        assert dec is not None and dec.tool is not None
        output, ok = run_tool(dec.tool, dec.input)
        call = ToolCall(
            tool=dec.tool,
            input=dec.input,
            output=output,
            step_index=len(state.tool_calls),
            ok=ok,
        )
        return {"tool_calls": state.tool_calls + [call]}

    def reflect_node(state: AgentState) -> dict:
        verdict = reflect(state, llm)
        if verdict.sufficient:
            return {"reflection": verdict}
        # Insufficient -> record what's missing and count this as another loop.
        note = verdict.missing or "Information judged insufficient."
        return {
            "reflection": verdict,
            "iteration": state.iteration + 1,
            "reflection_notes": state.reflection_notes + [note],
        }

    def finalize_node(state: AgentState) -> dict:
        return {"final_answer": build_final_answer(state, llm), "done": True}

    def route_after_planner(state: AgentState) -> str:
        if state.pending is None or state.pending.action == "finish":
            return "finish"
        return "tool"

    def route_after_reflect(state: AgentState) -> str:
        return "finish" if (state.reflection and state.reflection.sufficient) else "continue"

    g = StateGraph(AgentState)
    g.add_node("planner", planner_node)
    g.add_node("tool_executor", tool_executor_node)
    g.add_node("reflect", reflect_node)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("planner")
    g.add_conditional_edges(
        "planner", route_after_planner, {"tool": "tool_executor", "finish": "finalize"}
    )
    g.add_edge("tool_executor", "reflect")
    g.add_conditional_edges(
        "reflect", route_after_reflect, {"continue": "planner", "finish": "finalize"}
    )
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer or MemorySaver())


def run_query(
    query: str,
    llm: LLMProvider | None = None,
    max_iterations: int = 6,
    graph: Any | None = None,
) -> AgentState:
    """Convenience runner used by the API and the eval harness. Returns final state."""
    graph = graph or build_graph(llm=llm)
    init = AgentState(query=query, max_iterations=max_iterations)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 60}
    result = graph.invoke(init, config=config)
    # LangGraph returns the state as a dict-like; normalise back to AgentState.
    return AgentState.model_validate(result)
