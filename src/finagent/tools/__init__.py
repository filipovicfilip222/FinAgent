"""Tool registry + dispatcher.

Each tool is a plain ``dict -> str`` callable registered under a name the planner
uses. ``run_tool`` is the single entry point the graph's ``tool_executor`` calls; it
never raises to the graph — a failing tool returns ``(error_text, ok=False)`` so the
agent can reflect on the failure and try something else instead of crashing the run.
"""

from __future__ import annotations

from collections.abc import Callable

ToolFn = Callable[[dict], str]

_REGISTRY: dict[str, ToolFn] = {}


def register(name: str) -> Callable[[ToolFn], ToolFn]:
    def deco(fn: ToolFn) -> ToolFn:
        _REGISTRY[name] = fn
        return fn

    return deco


def available_tools() -> list[str]:
    return sorted(_REGISTRY)


def run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Execute a tool. Returns ``(output_text, ok)``; never raises."""
    fn = _REGISTRY.get(name)
    if fn is None:
        return (f"Tool '{name}' is not available. Registered: {available_tools()}", False)
    try:
        return (fn(tool_input or {}), True)
    except Exception as exc:  # noqa: BLE001 - tools must degrade gracefully
        return (f"{type(exc).__name__}: {exc}", False)


# Importing the submodules triggers their @register side effects. Kept lazy-tolerant:
# heavy/optional tools (RAG) may be unavailable in a minimal install, which is fine.
def _load_builtin_tools() -> None:
    from . import calculator  # noqa: F401  (pure, always available)

    for mod in ("sec_edgar", "web_search", "rag_retrieve"):
        try:
            __import__(f"{__name__}.{mod}")
        except Exception:  # noqa: BLE001 - optional deps (chromadb/voyage) may be missing
            pass


_load_builtin_tools()
