"""The LangGraph state object.

Using a Pydantic ``BaseModel`` (rather than a ``TypedDict``) as the graph state
gives us validation and a clean object to inspect after every checkpoint — handy
for both the eval harness and LangSmith traces.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .schemas import FinalAnswer, PlannerDecision, ReflectionDecision

ToolName = Literal["sec_edgar", "web_search", "calculator", "rag_retrieve"]


class ToolCall(BaseModel):
    """A record of one executed tool call (kept in state for planner/reflect/eval)."""

    tool: ToolName
    input: dict
    output: str
    step_index: int
    ok: bool = True  # False when the tool raised / returned an error string


class AgentState(BaseModel):
    query: str
    plan: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    reflection_notes: list[str] = Field(default_factory=list)
    iteration: int = 0
    max_iterations: int = 6
    final_answer: FinalAnswer | None = None
    done: bool = False

    # --- transient routing fields (set by nodes, read by conditional edges) ---
    # Not part of the "answer" — they just carry the latest planner/reflect verdict
    # between a node and the edge that routes on it.
    pending: PlannerDecision | None = None
    reflection: ReflectionDecision | None = None
    forced_finish: bool = False  # True when max_iterations cut the loop short

    # --- convenience helpers (used by nodes, prompts and the eval) ---

    @property
    def tools_used(self) -> list[str]:
        return [tc.tool for tc in self.tool_calls]

    @property
    def had_tool_error(self) -> bool:
        return any(not tc.ok for tc in self.tool_calls)

    def tool_history_summary(self, max_chars: int = 600) -> str:
        """Compact, human-readable summary of prior tool calls for the planner.

        We deliberately truncate raw outputs so the planner prompt stays small even
        after several steps.
        """
        if not self.tool_calls:
            return "(no tools called yet)"
        lines = []
        for tc in self.tool_calls:
            out = tc.output.replace("\n", " ")
            if len(out) > max_chars:
                out = out[:max_chars] + " …[truncated]"
            status = "" if tc.ok else " [ERROR]"
            lines.append(f"#{tc.step_index} {tc.tool}({tc.input}){status} -> {out}")
        return "\n".join(lines)
