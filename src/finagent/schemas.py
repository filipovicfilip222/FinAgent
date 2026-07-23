"""Pydantic schemas for structured output.

The whole point of routing the final answer (and the planner/reflect decisions)
through Pydantic is *numerical discipline*: the model must hand back typed
``key_numbers`` and explicit ``citations`` rather than free-form prose, which is
what makes the eval's numerical-accuracy check meaningful.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]


class Citation(BaseModel):
    """A single source the answer relies on."""

    source: str = Field(..., description='e.g. "SEC EDGAR 10-K AAPL FY2025" or a URL')
    detail: str = Field(..., description="what specifically from the source was used")


class FinalAnswer(BaseModel):
    """The structured contract returned by the ``finalize`` node."""

    answer: str = Field(..., description="natural-language answer to the user's question")
    key_numbers: dict[str, float] = Field(
        default_factory=dict,
        description="named numeric results, e.g. {'aapl_gross_margin_pct': 46.2}",
    )
    citations: list[Citation] = Field(default_factory=list)
    confidence: Confidence = "medium"
    caveats: str | None = Field(
        default=None,
        description="populated when data was missing, a tool errored, or the loop was cut short",
    )


# --- Planner / reflection decision schemas (also used as Claude tool schemas) ---


class PlannerDecision(BaseModel):
    """What the planner node decides on each turn."""

    action: Literal["call_tool", "finish"]
    tool: Literal["sec_edgar", "web_search", "calculator", "rag_retrieve"] | None = None
    input: dict = Field(default_factory=dict)
    reasoning: str = Field(..., description="why this action was chosen (shown in traces/eval)")


class ReflectionDecision(BaseModel):
    """Reflection verdict after a tool call."""

    sufficient: bool
    missing: str | None = Field(
        default=None, description="short description of what is still missing, or null"
    )
