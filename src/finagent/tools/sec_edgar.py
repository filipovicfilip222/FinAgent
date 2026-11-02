"""SEC EDGAR tool — official figures from XBRL ``companyconcept`` data.

Talks to ``https://data.sec.gov`` (free, no API key, but a descriptive
``User-Agent`` with a contact email is mandatory or SEC returns 403).

Two behaviours worth calling out:

* **Concept aliasing.** Companies tag the same economic line differently — Apple &
  Microsoft report revenue under ``RevenueFromContractWithCustomerExcludingAssessedTax``,
  not the textbook ``Revenues``. The tool tries a short alias list so the planner can
  just ask for "Revenues" and still get an answer.
* **Transparent on-disk cache.** Every successful live response is cached under
  ``data/fixtures/``; if the network is unavailable the tool serves the cached copy.
  This makes the eval reproducible (and rate-limit friendly) and lets it run fully
  offline from the committed fixtures.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import httpx

from ..config import get_settings
from . import register

# Static ticker -> CIK map (zero-padded to 10 digits). Enough for the demo/eval; a
# production build would pull the full company_tickers.json map.
TICKER_TO_CIK = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "META": "0001326801",
}

COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "META": "Meta Platforms Inc.",
}

# Friendly concept -> ordered list of real us-gaap tags to try.
CONCEPT_ALIASES = {
    "Revenues": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ],
    "NetIncomeLoss": ["NetIncomeLoss"],
    "GrossProfit": ["GrossProfit"],
    "OperatingIncomeLoss": ["OperatingIncomeLoss"],
    "ResearchAndDevelopmentExpense": ["ResearchAndDevelopmentExpense"],
}

BASE_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{tag}.json"


def _fixtures_dir() -> Path:
    d = get_settings().project_root / "data" / "fixtures"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(cik: str, tag: str) -> Path:
    return _fixtures_dir() / f"CIK{cik}_{tag}.json"


def _fetch_live(cik: str, tag: str) -> dict:
    url = BASE_URL.format(cik=cik, tag=tag)
    headers = {"User-Agent": get_settings().sec_user_agent, "Accept": "application/json"}
    resp = httpx.get(url, headers=headers, timeout=20.0)
    resp.raise_for_status()
    return resp.json()


def get_concept_json(cik: str, tag: str) -> tuple[dict, str]:
    """Return (data, source) for one concept tag.

    ``source`` is "live" or "cache". Mode is controlled by ``SEC_EDGAR_MODE``:
    ``auto`` (default) tries live then falls back to cache; ``cache`` forces the
    committed fixtures (used for deterministic eval runs); ``live`` forbids cache.
    """
    mode = os.getenv("SEC_EDGAR_MODE", "auto").lower()
    path = _cache_path(cik, tag)

    if mode == "cache":
        if not path.exists():
            raise FileNotFoundError(f"No cached fixture for CIK{cik}/{tag}")
        return json.loads(path.read_text()), "cache"

    try:
        data = _fetch_live(cik, tag)
        path.write_text(json.dumps(data))  # refresh cache on every successful call
        return data, "live"
    except Exception:
        if mode != "live" and path.exists():
            return json.loads(path.read_text()), "cache"
        raise


def _duration_days(entry: dict) -> int:
    try:
        s = date.fromisoformat(entry["start"])
        e = date.fromisoformat(entry["end"])
        return (e - s).days
    except Exception:
        return -1


def _dedupe_latest(entries: list[dict]) -> list[dict]:
    """Collapse duplicate (start,end) periods, keeping the most recently filed value."""
    best: dict[tuple[str, str], dict] = {}
    for e in entries:
        key = (e.get("start", ""), e.get("end", ""))
        cur = best.get(key)
        if cur is None or e.get("filed", "") > cur.get("filed", ""):
            best[key] = e
    return sorted(best.values(), key=lambda e: e.get("end", ""), reverse=True)


def _fmt_usd(val: float) -> str:
    return f"{val:,.0f}"


def _resolve_and_fetch(cik: str, concept: str) -> tuple[dict, str, str]:
    """Try the alias list; return (data, resolved_tag, source)."""
    tags = CONCEPT_ALIASES.get(concept, [concept])
    last_err: Exception | None = None
    for tag in tags:
        try:
            data, source = get_concept_json(cik, tag)
            return data, tag, source
        except Exception as exc:  # noqa: BLE001 - try next alias
            last_err = exc
            continue
    raise RuntimeError(
        f"Could not retrieve concept '{concept}' for CIK{cik} "
        f"(tried {tags}). Last error: {last_err}"
    )


def sec_edgar(tool_input: dict) -> str:
    ticker = str(tool_input.get("ticker", "")).upper().strip()
    concept = str(tool_input.get("concept", "Revenues")).strip() or "Revenues"
    n = int(tool_input.get("n", 4) or 4)

    if ticker not in TICKER_TO_CIK:
        return (
            f"Unknown ticker '{ticker}'. Known tickers: {sorted(TICKER_TO_CIK)}. "
            "(The demo ships with a small static ticker->CIK map.)"
        )
    cik = TICKER_TO_CIK[ticker]

    data, tag, source = _resolve_and_fetch(cik, concept)
    usd = data.get("units", {}).get("USD", [])
    if not usd:
        return f"No USD data points found for {ticker} concept {tag}."

    quarters = _dedupe_latest([e for e in usd if 60 <= _duration_days(e) <= 100])
    annuals = _dedupe_latest([e for e in usd if _duration_days(e) >= 300])

    name = COMPANY_NAMES.get(ticker, data.get("entityName", ticker))
    lines = [
        f"{name} ({ticker}, CIK {cik}) — us-gaap:{tag}, unit USD. [source: {source}]",
        f"Most recent quarterly figures (up to {n}):",
    ]
    for e in quarters[:n]:
        lines.append(
            f"  - FY{e.get('fy')} {e.get('fp')} ({e.get('start')} to {e.get('end')}): "
            f"{_fmt_usd(e['val'])}  [{e.get('form')}, accn {e.get('accn')}, filed {e.get('filed')}]"
        )
    if annuals:
        lines.append("Recent annual (fiscal-year) figures (10-K):")
        for e in annuals[:3]:
            lines.append(
                f"  - FY{e.get('fy')} ({e.get('start')} to {e.get('end')}): "
                f"{_fmt_usd(e['val'])}  [{e.get('form')}, filed {e.get('filed')}]"
            )
    return "\n".join(lines)


register("sec_edgar")(sec_edgar)
