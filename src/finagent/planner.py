"""Planner node.

The planner is the heart of the "agent decides, not a fixed pipeline" claim: given
the question and everything learned so far, it chooses **one** next action — call a
specific tool, or finish. It must always explain its choice (``reasoning``), which
is what the eval surfaces as "why did the agent pick this tool".
"""

from __future__ import annotations

from .llm import PLANNER_TOOL, LLMProvider
from .schemas import PlannerDecision
from .state import AgentState

PLANNER_SYSTEM = """You are the planner of a financial-research agent. On each turn you
choose exactly ONE next action based on the user's question and what has already been
gathered. You do not answer the question here — you route work to tools or decide you
have enough to finish.

You have four tools. Use them for what they are for:
- sec_edgar: official financial figures straight from SEC filings (10-K / 10-Q), e.g.
  revenue, net income, gross profit for a given company. Use this for any hard number
  that belongs in a filing.
- web_search: news, recent events, qualitative context that is NOT inside a filing
  (e.g. "what did analysts say this week", product announcements).
- calculator: arithmetic with more than one digit. You must NOT do multi-digit math in
  your head — margins, growth rates, percentage changes, and cross-company comparisons
  all go through the calculator. But do NOT call the calculator just to restate a number
  a tool already gave you: only use it to DERIVE new values (margin, growth, ratio, diff).
- rag_retrieve: retrieves passages from locally indexed filing PDFs. Use it for
  qualitative questions about filing content (risk factors, strategy, segment discussion).

Rules:
- Fetch each company's raw numbers BEFORE trying to compare or compute across companies.
- If the question compares two companies, make sure you have BOTH companies' data before
  finishing — otherwise the reflection step will (correctly) send you back.
- Prefer the smallest number of steps that actually answers the question.
- Always fill in `reasoning` with a short, concrete justification.
- When you already have everything needed, choose action="finish".
"""

PLANNER_TOOL_SCHEMA = {
    "name": PLANNER_TOOL,
    "description": "Choose the next action for the financial-research agent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["call_tool", "finish"],
                "description": "call a tool, or finish and hand off to the answer writer",
            },
            "tool": {
                "type": "string",
                "enum": ["sec_edgar", "web_search", "calculator", "rag_retrieve"],
                "description": "which tool to call (required when action=call_tool)",
            },
            "input": {
                "type": "object",
                "description": (
                    "arguments for the tool. sec_edgar: {ticker, concept, n}; "
                    "web_search: {query}; calculator: {expression}; rag_retrieve: {query, k}"
                ),
            },
            "reasoning": {
                "type": "string",
                "description": "short justification for this action",
            },
        },
        "required": ["action", "reasoning"],
    },
}


def build_planner_user(state: AgentState) -> str:
    parts = [
        f"USER QUESTION:\n{state.query}\n",
        f"TOOL CALLS SO FAR:\n{state.tool_history_summary()}\n",
    ]
    if state.reflection_notes:
        notes = "\n".join(f"- {n}" for n in state.reflection_notes)
        parts.append(
            "REFLECTION NOTES (things a previous check found still missing — address these):\n"
            f"{notes}\n"
        )
    parts.append(
        f"(iteration {state.iteration} of max {state.max_iterations}) "
        "Decide the next action."
    )
    return "\n".join(parts)


def plan(state: AgentState, llm: LLMProvider) -> PlannerDecision:
    raw = llm.complete_json(
        system=PLANNER_SYSTEM,
        user=build_planner_user(state),
        tool=PLANNER_TOOL_SCHEMA,
        context={"state": state},
    )
    decision = PlannerDecision.model_validate(raw)
    # Guard: a call_tool decision must name a tool; degrade to finish if malformed.
    if decision.action == "call_tool" and not decision.tool:
        return PlannerDecision(
            action="finish",
            reasoning="Planner requested a tool call without naming a tool; finishing instead.",
        )
    return decision
