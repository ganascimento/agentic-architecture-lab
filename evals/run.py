"""Runs the mini-eval against an agent architecture and saves the results for comparison.

Usage (venv active):
    python -m evals.run                  # all cases, 3 runs each
    python -m evals.run --runs 1 --case 10 11
"""

import argparse
import json
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from evals.cases import CASES, Case, RunResult
from src import data
from src.agent import ServiceDeskAgent

# Architectures under test. In lesson 1.3 we add "multi" here and run the SAME cases.
AGENTS: dict[str, Callable[[], ServiceDeskAgent]] = {
    "single": lambda: ServiceDeskAgent(verbose=False),
}

RESULTS_DIR = Path(__file__).parent / "results"


def run_case(case: Case, make_agent: Callable[[], ServiceDeskAgent]) -> RunResult:
    data.reset()  # every run starts from the same data
    agent = make_agent()
    start = time.perf_counter()
    replies = [agent.reply(turn) for turn in case.turns]
    return RunResult(
        reply=replies[-1],
        replies=replies,
        tool_calls=agent.tool_calls,
        calls=agent.usage.calls,
        cost=agent.usage.cost(agent.model.name),
        latency=time.perf_counter() - start,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=AGENTS, default="single")
    parser.add_argument("--runs", type=int, default=3, help="runs per case (the LLM varies between runs)")
    parser.add_argument("--case", type=int, nargs="*", help="only these case ids")
    args = parser.parse_args()

    cases = [c for c in CASES if not args.case or c.id in args.case]
    rows = []
    print(f"Agent: {args.agent} | {len(cases)} cases x {args.runs} runs\n")
    print(f"{'#':>3}  {'category':<9} {'pass':<6} {'calls':>5} {'cost US$':>9} {'time s':>7}  notes")

    for case in cases:
        runs = [run_case(case, AGENTS[args.agent]) for _ in range(args.runs)]
        failures = [[msg for check in case.checks if (msg := check(r))] for r in runs]
        passed = sum(1 for f in failures if not f)
        row = {
            "id": case.id, "category": case.category, "turns": case.turns,
            "passed": passed, "runs": args.runs, "known_failure": case.known_failure,
            "avg_calls": sum(r.calls for r in runs) / len(runs),
            "avg_cost": sum(r.cost for r in runs) / len(runs),
            "avg_latency": sum(r.latency for r in runs) / len(runs),
            "failures": [f for f in failures if f],
            "replies": [r.reply for r in runs],
            "tools": [[t.name for t in r.tool_calls] for r in runs],
        }
        rows.append(row)

        note = f"KNOWN: {case.known_failure}" if case.known_failure else ""
        if row["failures"] and not case.known_failure:
            note = "; ".join(sorted({msg for f in row["failures"] for msg in f}))
        mark = "✅" if passed == args.runs else ("❌" if passed == 0 else "⚠️")
        if case.known_failure:
            mark = "🔶"
        print(f"{case.id:>3}  {case.category:<9} {mark}{passed}/{args.runs:<3} {row['avg_calls']:>5.1f} "
              f"{row['avg_cost']:>9.5f} {row['avg_latency']:>7.1f}  {note}")

    scored = [r for r in rows if not r["known_failure"]]
    total_runs = sum(r["runs"] for r in scored)
    total_pass = sum(r["passed"] for r in scored)
    summary = {
        "agent": args.agent,
        "pass_rate": total_pass / total_runs if total_runs else 0.0,
        "avg_calls": sum(r["avg_calls"] for r in rows) / len(rows),
        "avg_cost": sum(r["avg_cost"] for r in rows) / len(rows),
        "avg_latency": sum(r["avg_latency"] for r in rows) / len(rows),
        "total_cost": sum(r["avg_cost"] * r["runs"] for r in rows),
    }
    print(f"\nPass rate (scored cases): {summary['pass_rate']:.0%} ({total_pass}/{total_runs})"
          f" | avg per case: {summary['avg_calls']:.1f} calls, US$ {summary['avg_cost']:.5f},"
          f" {summary['avg_latency']:.1f}s | eval total: US$ {summary['total_cost']:.4f}")
    print("🔶 = known failure (reported, not scored)")

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{args.agent}-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2))
    print(f"Saved: {out.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
