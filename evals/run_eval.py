"""Run the eval dataset through the agent and write a report.

Usage (from repo root):
    python evals/run_eval.py                      # full dataset, configured provider
    python evals/run_eval.py --provider mock      # offline smoke run (no key)
    python evals/run_eval.py --ids q07,q08,q18    # just a few (e.g. the reflection ones)
    python evals/run_eval.py --limit 5 --name report_smoke

Writes evals/results/<name>.md and <name>.json. Every question is run in isolation and
errors are captured per-question, so one failure never aborts the whole run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # so `import metrics` works
sys.path.insert(0, str(HERE.parent / "src"))  # so `import finagent` works without install

from finagent.graph import run_query  # noqa: E402
from finagent.llm import get_llm  # noqa: E402
from metrics import (  # noqa: E402
    QuestionResult,
    answer_contains,
    numeric_match,
    summarize,
    tool_selection,
)


def _run_one(item: dict, graph=None, max_iterations: int | None = None) -> QuestionResult:
    t0 = time.time()
    error = None
    try:
        mi = max_iterations or item.get("max_iterations", 6)
        state = run_query(item["query"], graph=graph, max_iterations=mi)
        answer = state.final_answer.answer if state.final_answer else ""
        key_numbers = dict(state.final_answer.key_numbers) if state.final_answer else {}
        confidence = state.final_answer.confidence if state.final_answer else "low"
        tools_used = state.tools_used
        reflection_notes = state.reflection_notes
        iterations = state.iteration
        n_tool_calls = len(state.tool_calls)
        had_tool_error = state.had_tool_error
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        answer, key_numbers, confidence = "", {}, "low"
        tools_used, reflection_notes = [], []
        iterations = n_tool_calls = 0
        had_tool_error = True

    latency = round(time.time() - t0, 2)
    exact, jacc = tool_selection(tools_used, item["expected_tools"])
    num = numeric_match(item.get("expected_number"), key_numbers, answer, item.get("tolerance_pct", 5))
    cont = answer_contains(answer, item.get("expected_answer_contains"))

    return QuestionResult(
        id=item["id"],
        category=item.get("category", "?"),
        difficulty=item.get("difficulty", "?"),
        query=item["query"],
        expected_tools=item["expected_tools"],
        tools_used=tools_used,
        tool_exact=exact,
        tool_jaccard=round(jacc, 3),
        numeric_applicable=item.get("expected_number") is not None,
        numeric_correct=num,
        contains_applicable=bool(item.get("expected_answer_contains")),
        contains_ok=cont,
        reflection_fired=len(reflection_notes) > 0,
        expect_reflection=bool(item.get("expect_reflection")),
        reflection_notes=reflection_notes,
        n_tool_calls=n_tool_calls,
        iterations=iterations,
        confidence=confidence,
        had_tool_error=had_tool_error,
        latency_s=latency,
        answer=answer,
        key_numbers=key_numbers,
        error=error,
    )


def _bool(v):
    return {True: "✓", False: "✗", None: "–"}[v]


def _markdown(summary, results, provider: str, when: str) -> str:
    s = summary
    ok = [r for r in results if r.error is None]
    tool_exact_k = sum(r.tool_exact for r in ok)
    refl_k = sum(r.reflection_fired for r in ok)
    lines = [
        "# FinAgent — Evaluation Report",
        "",
        f"- **Run at:** {when}",
        f"- **LLM provider:** `{provider}`",
        f"- **Questions:** {s.n}  ·  **Errors:** {s.errors}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Tool-selection accuracy (exact set) | {s.tool_exact_pct}% ({tool_exact_k}/{len(ok)}) |",
        f"| Tool-selection mean Jaccard | {s.tool_mean_jaccard} |",
        f"| Numerical accuracy (within tolerance) | {s.numeric_accuracy_pct}% (n={s.numeric_n}) |",
        f"| Answer-content checks passed | {s.contains_accuracy_pct}% (n={s.contains_n}) |",
        f"| Avg planner iterations | {s.avg_iterations} |",
        f"| Avg tool calls / question | {s.avg_tool_calls} |",
        f"| **Reflection trigger rate** | **{s.reflection_trigger_rate_pct}%** ({refl_k}/{len(ok)}) |",
        f"| Reflection recall on questions designed to need it | "
        f"{s.reflection_recall_pct}% (n={s.reflection_expected_n}) |",
        f"| Avg latency / question | {s.avg_latency_s}s |",
        f"| Confidence distribution | {json.dumps(s.confidence_counts)} |",
        "",
        "## Per-question results",
        "",
        "| id | diff | tools used | exp tools | tool | num | txt | refl(exp) | steps | conf | lat |",
        "|---|---|---|---|:--:|:--:|:--:|:--:|:--:|:--:|--:|",
    ]
    for r in results:
        refl = f"{_bool(r.reflection_fired)}({'y' if r.expect_reflection else 'n'})"
        lines.append(
            f"| {r.id} | {r.difficulty} | {','.join(r.tools_used) or '–'} | "
            f"{','.join(r.expected_tools)} | {_bool(r.tool_exact)} | {_bool(r.numeric_correct)} | "
            f"{_bool(r.contains_ok)} | {refl} | {r.n_tool_calls} | {r.confidence} | {r.latency_s}s |"
        )

    # Show the reflection questions in detail — this is the headline claim.
    refl_qs = [r for r in results if r.reflection_fired]
    lines += ["", "## Reflection loop — evidence it actually fired", ""]
    if not refl_qs:
        lines.append("_No question triggered the reflection loop in this run._")
    for r in refl_qs:
        lines.append(f"- **{r.id}** ({r.iterations} iteration(s)): {r.query}")
        for note in r.reflection_notes:
            lines.append(f"    - reflect → *insufficient*: {note}")

    # One worked example in full.
    example = next((r for r in results if r.reflection_fired and r.error is None),
                   results[0] if results else None)
    if example is not None:
        lines += ["", "## Example answer (full)", "", f"**Q ({example.id}):** {example.query}", ""]
        lines.append("```json")
        lines.append(json.dumps(
            {"answer": example.answer, "key_numbers": example.key_numbers,
             "confidence": example.confidence, "tools_used": example.tools_used}, indent=2))
        lines.append("```")
    return "\n".join(lines) + "\n"


def _partial_path(out_dir: Path, name: str, qid: str) -> Path:
    d = out_dir / f"_partial_{name}"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{qid}.json"


def _load_partial(path: Path) -> QuestionResult | None:
    if not path.exists():
        return None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        valid = {f.name for f in fields(QuestionResult)}
        return QuestionResult(**{k: v for k, v in d.items() if k in valid})
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(HERE / "dataset.json"))
    ap.add_argument("--provider", default=None, help="override LLM_PROVIDER (anthropic|openai|mock)")
    ap.add_argument("--ids", default=None, help="comma-separated subset of question ids")
    ap.add_argument("--category", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--name", default=None, help="output basename (default report_<ts>)")
    ap.add_argument("--out-dir", default=str(HERE / "results"))
    ap.add_argument("--concurrency", type=int, default=1, help="parallel questions")
    ap.add_argument("--fresh", action="store_true", help="ignore any cached partial results")
    ap.add_argument("--max-iterations", type=int, default=None, help="override loop cap per question")
    args = ap.parse_args(argv)

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    provider = get_llm().name

    items = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",")}
        items = [it for it in items if it["id"] in wanted]
    if args.category:
        items = [it for it in items if it.get("category") == args.category]
    if args.limit:
        items = items[: args.limit]

    name = args.name or f"report_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resume support: each finished question is written to a partial file; re-running
    # skips finished ones. This lets a long real run survive short-lived shells.
    results_by_id: dict[str, QuestionResult] = {}
    to_run: list[dict] = []
    for it in items:
        cached = None if args.fresh else _load_partial(_partial_path(out_dir, name, it["id"]))
        if cached is not None:
            results_by_id[it["id"]] = cached
        else:
            to_run.append(it)

    print(f"provider={provider} total={len(items)} cached={len(results_by_id)} "
          f"to_run={len(to_run)} concurrency={args.concurrency}")

    def worker(it: dict) -> QuestionResult:
        r = _run_one(it, max_iterations=args.max_iterations)  # own graph for thread isolation
        _partial_path(out_dir, name, it["id"]).write_text(
            json.dumps(r.to_dict(), indent=2), encoding="utf-8"
        )
        return r

    def _log(r: QuestionResult) -> None:
        extra = f" ERR={r.error}" if r.error else ""
        print(f"  {r.id}: tools={r.tools_used} refl={r.reflection_fired} "
              f"conf={r.confidence} num={r.numeric_correct} {r.latency_s}s{extra}", flush=True)

    if to_run and args.concurrency > 1:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(worker, it): it for it in to_run}
            for fut in as_completed(futs):
                r = fut.result()
                results_by_id[r.id] = r
                _log(r)
    else:
        for it in to_run:
            r = worker(it)
            results_by_id[it["id"]] = r
            _log(r)

    results = [results_by_id[it["id"]] for it in items if it["id"] in results_by_id]
    missing = [it["id"] for it in items if it["id"] not in results_by_id]
    summary = summarize(results)
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    # Explicit UTF-8: the report uses ✓/✗, which the Windows default code page can't encode.
    (out_dir / f"{name}.md").write_text(
        _markdown(summary, results, provider, when), encoding="utf-8"
    )
    (out_dir / f"{name}.json").write_text(json.dumps(
        {"provider": provider, "when": when, "summary": summary.to_dict(),
         "results": [r.to_dict() for r in results], "missing": missing}, indent=2),
        encoding="utf-8")

    print("\n=== SUMMARY ===")
    print(json.dumps(summary.to_dict(), indent=2))
    if missing:
        print(f"\nMISSING {len(missing)} (re-run same command to finish): {missing}")
    else:
        print(f"\nALL {len(results)} done. Wrote {out_dir / (name + '.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
