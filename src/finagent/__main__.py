"""CLI entry point.

    python -m finagent "What was Apple's net margin in FY2025?"
    python -m finagent --json "Compare Apple and Microsoft revenue"
    python -m finagent --provider mock "hello"     # offline, no key
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent", description="Ask the FinAgent a question.")
    ap.add_argument("query", nargs="+", help="the question to ask")
    ap.add_argument("--provider", default=None, help="LLM_PROVIDER override (anthropic|openai|mock)")
    ap.add_argument("--json", action="store_true", help="print the raw FinalAnswer JSON")
    ap.add_argument("--max-iterations", type=int, default=6)
    args = ap.parse_args(argv)

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    from .graph import run_query  # imported after env is set

    state = run_query(" ".join(args.query), max_iterations=args.max_iterations)
    fa = state.final_answer
    if args.json:
        print(json.dumps(fa.model_dump() if fa else {}, indent=2))
        return 0

    print(f"\nQ: {state.query}\n")
    print(fa.answer if fa else "(no answer)")
    if fa and fa.key_numbers:
        print("\nKey numbers:")
        for k, v in fa.key_numbers.items():
            print(f"  - {k}: {v:,}")
    if fa and fa.citations:
        print("\nSources:")
        for c in fa.citations:
            print(f"  - {c.source}: {c.detail}")
    print(f"\nconfidence: {fa.confidence if fa else 'n/a'}"
          f"  ·  tools: {', '.join(state.tools_used) or 'none'}"
          f"  ·  iterations: {state.iteration}")
    if fa and fa.caveats:
        print(f"caveats: {fa.caveats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
