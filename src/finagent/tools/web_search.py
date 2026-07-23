"""Web-search tool.

Default provider is Anthropic's server-side ``web_search`` tool, which we chose over
Tavily for one concrete reason: it reuses the Anthropic key the agent already needs,
so there is no second API credential to manage. Tavily is wired as an alternative,
and a ``stub`` provider keeps offline/CI runs (and the mock LLM) from failing.

Results are returned as a compact text block with titles + URLs so the finalize node
can turn them into citations.
"""

from __future__ import annotations

from ..config import get_settings
from . import register


def _stub(query: str) -> str:
    return (
        f"[web_search stub] No live web provider configured (offline/CI). "
        f"Query was: {query!r}. Set WEB_SEARCH_PROVIDER=anthropic (with ANTHROPIC_API_KEY) "
        f"or =tavily (with TAVILY_API_KEY) to enable real search."
    )


def _anthropic_web_search(query: str, max_results: int = 5) -> str:
    import anthropic

    s = get_settings()
    if not s.anthropic_api_key:
        return _stub(query)
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    resp = client.messages.create(
        model=s.model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Search the web and summarise the most relevant, recent findings for: "
                    f"{query}\nGive a 2-3 sentence synthesis, then list the sources you used."
                ),
            }
        ],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
    )

    summary_parts: list[str] = []
    sources: list[str] = []
    for block in resp.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            summary_parts.append(block.text)
        elif btype == "web_search_tool_result":
            for item in getattr(block, "content", []) or []:
                title = getattr(item, "title", None)
                url = getattr(item, "url", None)
                if url:
                    sources.append(f"- {title or url} — {url}")
                    if len(sources) >= max_results:
                        break
    out = "".join(summary_parts).strip() or "(no synthesis returned)"
    if sources:
        out += "\n\nSources:\n" + "\n".join(sources)
    return out


def _tavily(query: str, max_results: int = 5) -> str:
    from tavily import TavilyClient

    s = get_settings()
    if not s.tavily_api_key:
        return _stub(query)
    client = TavilyClient(api_key=s.tavily_api_key)
    res = client.search(query=query, max_results=max_results)
    lines = [res.get("answer") or "(no direct answer)"]
    lines.append("\nSources:")
    for r in res.get("results", []):
        lines.append(f"- {r.get('title')} — {r.get('url')}")
    return "\n".join(lines)


def web_search(tool_input: dict) -> str:
    query = str(tool_input.get("query", "")).strip()
    if not query:
        return "web_search requires a non-empty 'query'."
    provider = get_settings().web_search_provider
    if provider == "anthropic":
        return _anthropic_web_search(query)
    if provider == "tavily":
        return _tavily(query)
    return _stub(query)


register("web_search")(web_search)
