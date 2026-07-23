"""Graph-level tests using the deterministic mock provider.

These prove the *control flow* without any API key:
- a trivial query finishes with no tools,
- a single-company query routes to SEC,
- a two-company comparison genuinely fires the reflection loop,
- and the max_iterations hard stop forces a finish with low confidence.
"""

from finagent.graph import run_query
from finagent.llm import FINAL_TOOL, PLANNER_TOOL, REFLECT_TOOL


def test_trivial_query_finishes_without_tools():
    s = run_query("Say hello, nothing financial.")
    assert s.done and s.final_answer is not None
    assert s.tools_used == []


def test_single_company_routes_to_sec():
    s = run_query("What was Apple's most recent quarterly revenue?")
    assert "sec_edgar" in s.tools_used
    assert s.final_answer is not None


def test_two_company_comparison_triggers_reflection():
    s = run_query("Compare Apple's and Microsoft's net margin.")
    # reflection must have fired at least once (the whole point of the project)
    assert len(s.reflection_notes) >= 1
    assert any("MSFT" in n for n in s.reflection_notes)
    # both companies were eventually fetched
    assert s.tools_used.count("sec_edgar") >= 2
    assert s.iteration >= 1


class _AlwaysInsufficient:
    """A provider that never accepts the evidence — used to exercise the hard stop."""

    name = "always_insufficient"

    def complete_json(self, *, system, user, tool, context=None, model=None):
        if tool["name"] == PLANNER_TOOL:
            return {"action": "call_tool", "tool": "calculator",
                    "input": {"expression": "1 + 1"}, "reasoning": "loop"}
        if tool["name"] == REFLECT_TOOL:
            return {"sufficient": False, "missing": "never enough"}
        if tool["name"] == FINAL_TOOL:
            return {"answer": "partial", "key_numbers": {}, "citations": [],
                    "confidence": "high", "caveats": None}
        raise AssertionError(tool["name"])


def test_max_iterations_forces_finish_with_low_confidence():
    s = run_query("loop forever please", llm=_AlwaysInsufficient(), max_iterations=3)
    assert s.forced_finish is True
    assert s.iteration == 3
    # confidence must be downgraded to low because the loop was cut short
    assert s.final_answer.confidence == "low"
    assert "iteration cap" in (s.final_answer.caveats or "")
