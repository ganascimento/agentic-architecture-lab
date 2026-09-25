"""Runs the mini-eval against an agent architecture and saves the results for comparison.

Usage (venv active):
    python -m evals.run                         # single agent, all cases, 3 runs each
    python -m evals.run --arch handoff          # single | routing | handoff | hub
    python -m evals.run --runs 1 --case 10 11
"""

import argparse
import json
import time
from datetime import datetime
from statistics import fmean
from pathlib import Path

import openai

from evals.cases import CASES, Case, RunResult
from src import data
from src.architectures import ARCHITECTURES
from src.auth import session_for

RESULTS_DIR = Path(__file__).parent / "results"


def run_case(case: Case, arch: str) -> RunResult:
    data.reset()  # every run starts from the same data
    agent = ARCHITECTURES[arch](session_for(case.user), False)  # the case's user is already logged in
    start = time.perf_counter()
    replies = [agent.reply(turn) for turn in case.turns]
    return RunResult(
        replies=replies,
        tool_calls=agent.tool_calls,
        calls=agent.usage.calls,
        cost=agent.cost(),
        latency=time.perf_counter() - start,
    )


def run_case_with_retry(case: Case, arch: str, attempts: int = 3) -> RunResult:
    """A network blip or a 5xx/429 from the API says nothing about the agent: retry the whole run (from clean
    data) instead of crashing the eval. Any other exception still crashes on purpose — that's a bug."""
    for attempt in range(1, attempts + 1):
        try:
            return run_case(case, arch)
        except (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError,
                openai.RateLimitError):
            if attempt == attempts:
                raise
            print(f"  (case {case.id}: connection error, retrying {attempt}/{attempts - 1})")
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", choices=ARCHITECTURES, default="single")
    parser.add_argument("--runs", type=int, default=3, help="runs per case (the LLM varies between runs)")
    parser.add_argument("--case", type=int, nargs="*", help="only these case ids")
    args = parser.parse_args()

    cases = [c for c in CASES if not args.case or c.id in args.case]
    rows = []
    print(f"Architecture: {args.arch} | {len(cases)} cases x {args.runs} runs\n")
    print(f"{'#':>3}  {'category':<9} {'pass':<6} {'calls':>5} {'cost US$':>9} {'time s':>7}  notes")

    for case in cases:
        runs = [run_case_with_retry(case, args.arch) for _ in range(args.runs)]
        failures = [[msg for check in case.checks if (msg := check(r))] for r in runs]
        passed = sum(1 for f in failures if not f)
        row = {
            "id": case.id, "category": case.category, "turns": case.turns,
            "passed": passed, "runs": args.runs,
            "avg_calls": fmean(r.calls for r in runs),
            "avg_cost": fmean(r.cost for r in runs),
            "avg_latency": fmean(r.latency for r in runs),
            "failures": [f for f in failures if f],
            "replies": [r.replies[-1] for r in runs],  # final reply of each run
            "tools": [[t.name for t in r.tool_calls] for r in runs],
            # Arguments too: without them you can't tell WHY a call failed (e.g. an invented justification).
            "tool_args": [[{t.name: t.arguments} for t in r.tool_calls] for r in runs],
        }
        rows.append(row)

        note = "; ".join(sorted({msg for f in row["failures"] for msg in f}))
        mark = "✅" if passed == args.runs else ("❌" if passed == 0 else "⚠️")
        print(f"{case.id:>3}  {case.category:<9} {mark}{passed}/{args.runs:<3} {row['avg_calls']:>5.1f} "
              f"{row['avg_cost']:>9.5f} {row['avg_latency']:>7.1f}  {note}")

    total_runs = sum(r["runs"] for r in rows)
    total_pass = sum(r["passed"] for r in rows)
    summary = {
        "arch": args.arch,
        "pass_rate": total_pass / total_runs if total_runs else 0.0,
        "avg_calls": fmean(r["avg_calls"] for r in rows),
        "avg_cost": fmean(r["avg_cost"] for r in rows),
        "avg_latency": fmean(r["avg_latency"] for r in rows),
        "total_cost": sum(r["avg_cost"] * r["runs"] for r in rows),
    }
    print(f"\nPass rate: {summary['pass_rate']:.0%} ({total_pass}/{total_runs})"
          f" | avg per case: {summary['avg_calls']:.1f} calls, US$ {summary['avg_cost']:.5f},"
          f" {summary['avg_latency']:.1f}s | eval total: US$ {summary['total_cost']:.4f}")

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{args.arch}-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2))
    print(f"Saved: {out.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
