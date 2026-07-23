"""Capture / refresh SEC EDGAR fixtures used by the offline eval.

The repo ships a small set of fixtures (Apple & Microsoft revenue and net income) so
the eval is reproducible without hitting SEC. Run this on a machine with network access
to refresh them or add more (ticker, concept) pairs:

    python scripts/capture_fixtures.py
    python scripts/capture_fixtures.py --ticker GOOGL --concept Revenues

Requires a valid SEC_EDGAR_USER_AGENT (see .env.example). Data © SEC EDGAR (public).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finagent.tools.sec_edgar import (  # noqa: E402
    CONCEPT_ALIASES,
    TICKER_TO_CIK,
    _cache_path,
    _fetch_live,
)

# Default set captured for the demo/eval.
DEFAULT_PAIRS = [
    ("AAPL", "Revenues"),
    ("AAPL", "NetIncomeLoss"),
    ("MSFT", "Revenues"),
    ("MSFT", "NetIncomeLoss"),
]


def capture(ticker: str, concept: str) -> str:
    cik = TICKER_TO_CIK[ticker]
    for tag in CONCEPT_ALIASES.get(concept, [concept]):
        try:
            data = _fetch_live(cik, tag)
        except Exception:
            continue
        if data.get("units", {}).get("USD"):
            path = _cache_path(cik, tag)
            import json

            path.write_text(json.dumps(data))
            return f"{ticker} {concept} -> {tag}: {len(data['units']['USD'])} points -> {path.name}"
    return f"{ticker} {concept}: FAILED (no alias returned data)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker")
    ap.add_argument("--concept")
    args = ap.parse_args(argv)
    pairs = [(args.ticker, args.concept)] if args.ticker and args.concept else DEFAULT_PAIRS
    for tk, concept in pairs:
        print(capture(tk, concept))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
