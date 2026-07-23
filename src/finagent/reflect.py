"""Reflection node.

Runs after every tool call and asks a deliberately skeptical question: *given what
we now have, can we fully answer — or is something still missing?* If something is
missing it says so, the note is fed back to the planner, and the loop continues.

The prompt carries a concrete "not sufficient" example on purpose: without it, models
strongly prefer to declare success early just to stop, which would make the whole
reflection mechanism decorative. That directly contradicts the project's goal.
"""

from __future__ import annotations

from .llm import REFLECT_TOOL, LLMProvider
from .schemas import ReflectionDecision
from .state import AgentState

REFLECT_SYSTEM = """You are the reflection checker of a financial-research agent. After a
tool call, decide whether the information gathered SO FAR is enough to fully and
correctly answer the user's question. Be skeptical — it is better to take one more step
than to answer with a gap.

Return sufficient=false (with a short `missing`) whenever the question is not yet fully
covered. Concrete example of NOT sufficient:
  Question: "How does Apple's gross margin compare with Microsoft's?"
  Gathered: Apple's gross profit and revenue only.
  -> sufficient=false, missing="Microsoft's gross profit and revenue have not been
     retrieved, so the comparison cannot be made yet."

Return sufficient=true only when every entity, number, and derived value the question
asks for is actually present in the gathered data (not merely assumed). If a required
calculation (margin, growth, comparison) has not been computed yet, that is NOT
sufficient.
"""

REFLECT_TOOL_SCHEMA = {
    "name": REFLECT_TOOL,
    "description": "Judge whether gathered information is sufficient to answer.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sufficient": {
                "type": "boolean",
                "description": "true only if the question can now be fully answered",
            },
            "missing": {
                "type": "string",
                "description": "short description of what is still missing (omit if sufficient)",
            },
        },
        "required": ["sufficient"],
    },
}


def build_reflect_user(state: AgentState) -> str:
    return (
        f"USER QUESTION:\n{state.query}\n\n"
        f"INFORMATION GATHERED SO FAR:\n{state.tool_history_summary()}\n\n"
        "Is this sufficient to fully answer the question?"
    )


def reflect(state: AgentState, llm: LLMProvider) -> ReflectionDecision:
    raw = llm.complete_json(
        system=REFLECT_SYSTEM,
        user=build_reflect_user(state),
        tool=REFLECT_TOOL_SCHEMA,
        context={"state": state},
        model=None,  # graph passes the reflect model via provider default
    )
    return ReflectionDecision.model_validate(raw)
