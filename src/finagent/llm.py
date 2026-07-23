"""LLM provider abstraction.

The graph's reasoning nodes (planner / reflect / finalize) never import an SDK
directly — they go through :class:`LLMProvider`. This gives us three things:

* a real **Anthropic** provider (the default; also what the committed eval uses),
* an optional **OpenAI** provider for the A/B comparison the plan calls for,
* a deterministic **mock** provider so the whole graph — including the reflection
  loop — runs in tests / CI with no API key and no network.

Every provider exposes one primitive, :meth:`complete_json`, which forces the
model to return a single JSON object matching a tool schema (Claude tool-use /
OpenAI function-calling). The mock inspects the tool name + supplied ``context``
to return a schema-valid dict heuristically.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol, runtime_checkable

from .config import get_settings

# Tool schema *names* — the provider dispatches on these.
PLANNER_TOOL = "planner_decision"
REFLECT_TOOL = "reflection"
FINAL_TOOL = "final_answer"


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        tool: dict[str, Any],
        context: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Return a dict matching ``tool['input_schema']`` (forced tool-use)."""
        ...


# --------------------------------------------------------------------------- #
# Anthropic (default)
# --------------------------------------------------------------------------- #
class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        import anthropic  # imported lazily so `mock` works without the extra installed

        s = get_settings()
        if not s.anthropic_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty. "
                "Set it in .env, or use LLM_PROVIDER=mock for offline runs."
            )
        self._client = anthropic.Anthropic(api_key=s.anthropic_api_key)
        self._model = s.model

    @property
    def client(self):  # exposed for the web_search tool (server-side tool call)
        return self._client

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        tool: dict[str, Any],
        context: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        resp = self._client.messages.create(
            model=model or self._model,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
                return dict(block.input)
        raise RuntimeError(f"Anthropic did not return the forced tool '{tool['name']}'.")


# --------------------------------------------------------------------------- #
# OpenAI (optional, for A/B eval)
# --------------------------------------------------------------------------- #
class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        from openai import OpenAI

        s = get_settings()
        if not s.openai_api_key:
            raise RuntimeError("LLM_PROVIDER=openai but OPENAI_API_KEY is empty.")
        self._client = OpenAI(api_key=s.openai_api_key)
        self._model = s.openai_model

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        tool: dict[str, Any],
        context: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        fn = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool["input_schema"],
            },
        }
        resp = self._client.chat.completions.create(
            model=model or self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[fn],
            tool_choice={"type": "function", "function": {"name": tool["name"]}},
        )
        call = resp.choices[0].message.tool_calls[0]
        return json.loads(call.function.arguments)


# --------------------------------------------------------------------------- #
# Mock (deterministic; no key, no network)
# --------------------------------------------------------------------------- #
_COMPANIES = {
    "apple": "AAPL",
    "aapl": "AAPL",
    "microsoft": "MSFT",
    "msft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "googl": "GOOGL",
    "amazon": "AMZN",
    "amzn": "AMZN",
    "meta": "META",
    "facebook": "META",
}

_CALC_HINTS = ("margin", "marža", "marza", "growth", "rast", "change", "promen",
               "percent", "procen", "compare", "pored", "razlik", "ratio", "cagr")
_RAG_HINTS = ("risk", "rizik", "strategy", "strategij", "segment", "management",
              "10-k", "10k", "guidance", "outlook")
_NEWS_HINTS = ("news", "vest", "latest", "najnovij", "announced", "objav", "today", "recent")


def _mentioned_tickers(text: str) -> list[str]:
    t = text.lower()
    seen: list[str] = []
    for kw, ticker in _COMPANIES.items():
        if re.search(rf"\b{re.escape(kw)}\b", t) and ticker not in seen:
            seen.append(ticker)
    return seen


class MockProvider:
    """Heuristic stand-in used by tests and CI.

    It decides *which* tool to use (the tool outputs themselves are still real —
    the calculator really computes, SEC reads from the fixture cache, etc.). The
    heuristics are intentionally simple; their job is to exercise the graph and,
    crucially, to make the reflection loop genuinely fire on multi-entity queries.
    """

    name = "mock"

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        tool: dict[str, Any],
        context: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        ctx = context or {}
        state = ctx.get("state")
        if tool["name"] == PLANNER_TOOL:
            return self._plan(state)
        if tool["name"] == REFLECT_TOOL:
            return self._reflect(state)
        if tool["name"] == FINAL_TOOL:
            return self._finalize(state)
        raise ValueError(f"MockProvider got unknown tool '{tool['name']}'")

    # -- helpers over AgentState-like object --
    @staticmethod
    def _query(state) -> str:
        return getattr(state, "query", "") if state is not None else ""

    @staticmethod
    def _calls(state):
        return getattr(state, "tool_calls", []) if state is not None else []

    def _fetched_tickers(self, state) -> list[str]:
        out = []
        for tc in self._calls(state):
            if tc.tool == "sec_edgar":
                tk = str(tc.input.get("ticker", "")).upper()
                if tk and tk not in out:
                    out.append(tk)
        return out

    def _plan(self, state) -> dict[str, Any]:
        q = self._query(state)
        want = _mentioned_tickers(q)
        have = self._fetched_tickers(state)
        # 1) fetch each mentioned company's numbers first
        for tk in want:
            if tk not in have:
                concept = "NetIncomeLoss" if any(h in q.lower() for h in ("income", "profit", "dobit", "neto")) else "Revenues"
                return {
                    "action": "call_tool",
                    "tool": "sec_edgar",
                    "input": {"ticker": tk, "concept": concept, "n": 4},
                    "reasoning": f"Need official filing figures for {tk} from SEC EDGAR before comparing/computing.",
                }
        used = [tc.tool for tc in self._calls(state)]
        low = q.lower()
        # 2) RAG questions
        if any(h in low for h in _RAG_HINTS) and "rag_retrieve" not in used:
            return {
                "action": "call_tool",
                "tool": "rag_retrieve",
                "input": {"query": q, "k": 4},
                "reasoning": "Question targets qualitative 10-K content; retrieve from indexed filings.",
            }
        # 3) news/context
        if any(h in low for h in _NEWS_HINTS) and "web_search" not in used:
            return {
                "action": "call_tool",
                "tool": "web_search",
                "input": {"query": q},
                "reasoning": "Question needs recent context beyond the filings.",
            }
        # 4) derived calculation
        if any(h in low for h in _CALC_HINTS) and "calculator" not in used:
            nums = self._recent_numbers(state)
            if len(nums) >= 2:
                a, b = nums[0], nums[1]
                expr = f"({a} - {b}) / {b} * 100"
                return {
                    "action": "call_tool",
                    "tool": "calculator",
                    "input": {"expression": expr},
                    "reasoning": "Compute the requested derived figure from fetched numbers (no mental math).",
                }
        return {"action": "finish", "reasoning": "Have enough to answer."}

    def _reflect(self, state) -> dict[str, Any]:
        q = self._query(state)
        want = _mentioned_tickers(q)
        have = self._fetched_tickers(state)
        missing = [t for t in want if t not in have]
        if len(want) >= 2 and missing:
            return {
                "sufficient": False,
                "missing": f"Comparison requested but no data yet for {', '.join(missing)}.",
            }
        if self._calls(state) and self._calls(state)[-1].ok is False:
            return {"sufficient": False, "missing": "Last tool call errored; try an alternative."}
        return {"sufficient": True, "missing": None}

    @staticmethod
    def _recent_numbers(state) -> list[float]:
        nums: list[float] = []
        for tc in reversed(getattr(state, "tool_calls", [])):
            if tc.tool == "sec_edgar":
                found = re.findall(r"[-+]?\d[\d,]*\.?\d*", tc.output.replace(",", ""))
                for f in found:
                    try:
                        nums.append(float(f))
                    except ValueError:
                        pass
                if len(nums) >= 2:
                    break
        return nums

    def _finalize(self, state) -> dict[str, Any]:
        calls = self._calls(state)
        key_numbers: dict[str, float] = {}
        for tc in calls:
            if tc.tool == "calculator":
                m = re.search(r"=\s*([-+]?\d[\d.]*)", tc.output)
                if m:
                    key_numbers["result"] = float(m.group(1))
        citations = []
        for tc in calls:
            if tc.tool == "sec_edgar" and tc.ok:
                citations.append({"source": f"SEC EDGAR ({tc.input.get('ticker','')})",
                                  "detail": f"{tc.input.get('concept','')} figures"})
            elif tc.tool == "rag_retrieve" and tc.ok:
                citations.append({"source": "Indexed 10-K filings", "detail": "retrieved passages"})
            elif tc.tool == "web_search" and tc.ok:
                citations.append({"source": "Web search", "detail": "recent context"})
        had_error = any(not tc.ok for tc in calls)
        hit_cap = getattr(state, "iteration", 0) >= getattr(state, "max_iterations", 6)
        confidence = "low" if (had_error or hit_cap) else ("high" if citations else "medium")
        answer = (
            f"[mock] Answer to: {self._query(state)!r}. "
            f"Used tools: {', '.join(tc.tool for tc in calls) or 'none'}."
        )
        return {
            "answer": answer,
            "key_numbers": key_numbers,
            "citations": citations or [{"source": "n/a", "detail": "no tools produced a citation"}],
            "confidence": confidence,
            "caveats": "Mock provider (offline)." + (" A tool errored." if had_error else ""),
        }


# --------------------------------------------------------------------------- #
_PROVIDERS = {"anthropic": AnthropicProvider, "openai": OpenAIProvider, "mock": MockProvider}


def get_llm(provider: str | None = None) -> LLMProvider:
    """Factory: build the configured provider (``LLM_PROVIDER`` unless overridden)."""
    name = (provider or get_settings().llm_provider or "anthropic").lower()
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER '{name}'. Choose from {sorted(_PROVIDERS)}.")
    return _PROVIDERS[name]()
