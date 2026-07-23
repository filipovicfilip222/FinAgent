"""Eval metrics.

Kept deliberately small and transparent (no framework) so it's easy to explain what
every number means:

* tool-selection accuracy  — did the agent use the tools we expected? (exact + Jaccard)
* numerical accuracy       — is the reported number within tolerance? (scale-invariant,
                             so 416.161 / 416161 / 416161000000 all count as the same
                             value expressed in different units)
* avg steps                — mean planner iterations / tool calls
* reflection-trigger rate  — share of questions where reflection said "not sufficient"
                             at least once (the proof the loop is real, not decorative)
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

_SCALES = [1, 1e3, 1e6, 1e9, 1e-3, 1e-6, 1e-9]
_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def tool_selection(used: list[str], expected: list[str]) -> tuple[bool, float]:
    su, se = set(used), set(expected)
    if not se:
        return (True, 1.0)
    inter = len(su & se)
    union = len(su | se)
    jaccard = inter / union if union else 1.0
    return (su == se, jaccard)


def _numbers_from_text(text: str) -> list[float]:
    out = []
    for tok in _NUM_RE.findall(text or ""):
        try:
            out.append(float(tok.replace(",", "")))
        except ValueError:
            pass
    return out


def numeric_match(
    expected: float | None, key_numbers: dict[str, float], answer_text: str, tol_pct: float
) -> bool | None:
    """Return True/False if a number was expected, else None (not applicable).

    Scale-invariant: a candidate matches if it equals ``expected`` within ``tol_pct``
    under any common unit scale (so billions vs raw dollars don't cause false misses).
    """
    if expected is None:
        return None
    if expected == 0:
        tol = tol_pct / 100.0
        candidates = list(key_numbers.values()) + _numbers_from_text(answer_text)
        return any(abs(c) <= tol for c in candidates)
    tol = abs(expected) * (tol_pct / 100.0)
    candidates = list(key_numbers.values()) + _numbers_from_text(answer_text)
    for c in candidates:
        for scale in _SCALES:
            if abs(c * scale - expected) <= tol:
                return True
    return False


def answer_contains(answer_text: str, needles: list[str] | None) -> bool | None:
    if not needles:
        return None
    low = (answer_text or "").lower()
    return all(n.lower() in low for n in needles)


@dataclass
class QuestionResult:
    id: str
    category: str
    difficulty: str
    query: str
    expected_tools: list[str]
    tools_used: list[str]
    tool_exact: bool
    tool_jaccard: float
    numeric_applicable: bool
    numeric_correct: bool | None
    contains_applicable: bool
    contains_ok: bool | None
    reflection_fired: bool
    expect_reflection: bool
    reflection_notes: list[str]
    n_tool_calls: int
    iterations: int
    confidence: str
    had_tool_error: bool
    latency_s: float
    answer: str
    key_numbers: dict[str, float]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Summary:
    n: int
    tool_exact_pct: float
    tool_mean_jaccard: float
    numeric_n: int
    numeric_accuracy_pct: float
    contains_n: int
    contains_accuracy_pct: float
    avg_tool_calls: float
    avg_iterations: float
    reflection_trigger_rate_pct: float
    reflection_recall_pct: float
    reflection_expected_n: int
    avg_latency_s: float
    confidence_counts: dict[str, int] = field(default_factory=dict)
    errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize(results: list[QuestionResult]) -> Summary:
    n = len(results)
    ok = [r for r in results if r.error is None]

    def pct(num, den):
        return round(100.0 * num / den, 1) if den else 0.0

    numeric_apps = [r for r in ok if r.numeric_applicable]
    contains_apps = [r for r in ok if r.contains_applicable]
    expected_reflection = [r for r in ok if r.expect_reflection]

    conf_counts: dict[str, int] = {}
    for r in ok:
        conf_counts[r.confidence] = conf_counts.get(r.confidence, 0) + 1

    return Summary(
        n=n,
        tool_exact_pct=pct(sum(r.tool_exact for r in ok), len(ok)),
        tool_mean_jaccard=round(sum(r.tool_jaccard for r in ok) / len(ok), 3) if ok else 0.0,
        numeric_n=len(numeric_apps),
        numeric_accuracy_pct=pct(sum(1 for r in numeric_apps if r.numeric_correct), len(numeric_apps)),
        contains_n=len(contains_apps),
        contains_accuracy_pct=pct(sum(1 for r in contains_apps if r.contains_ok), len(contains_apps)),
        avg_tool_calls=round(sum(r.n_tool_calls for r in ok) / len(ok), 2) if ok else 0.0,
        avg_iterations=round(sum(r.iterations for r in ok) / len(ok), 2) if ok else 0.0,
        reflection_trigger_rate_pct=pct(sum(r.reflection_fired for r in ok), len(ok)),
        reflection_recall_pct=pct(
            sum(1 for r in expected_reflection if r.reflection_fired), len(expected_reflection)
        ),
        reflection_expected_n=len(expected_reflection),
        avg_latency_s=round(sum(r.latency_s for r in ok) / len(ok), 2) if ok else 0.0,
        confidence_counts=conf_counts,
        errors=sum(1 for r in results if r.error is not None),
    )
