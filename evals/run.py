"""Runs the eval against the current Service Desk (a regression suite since module 2) and saves the results.

The IAM team's Access agent and the five MCP servers (the company's systems) are started here, in threads on
free ports — so the eval needs nothing else running, and can reset their data between runs too (only because
they run in OUR process: nobody outside a server can reset it — on purpose). Past modules' numbers: notes/SUMMARY.md and the module branches.

Usage (venv active):
    python -m evals.run                         # all cases, 3 runs each
    python -m evals.run --runs 1 --case 10 11
    python -m evals.run --topology supervisor   # lesson 4.5: the same cases on the supervisor topology
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from statistics import fmean

import openai

from evals.cases import CASES, Case, RunResult
from src.architectures import service_desk
from src.auth import session_for
from src.config import mcp_urls
from src.services import mcp_client
from src.services.a2a_client import A2AClient
from src.services.access_a2a import data as iam_data
from src.services.access_a2a.agent import access_agent_for
from src.services.access_a2a.server import AccessExecutor, start
from src.services.mcp_servers import server as mcp_servers
from src.tools._schema import Tool

RESULTS_DIR = Path(__file__).parent / "results"


def run_case(
    case: Case, access: AccessExecutor, client: A2AClient, tools: dict[str, Tool], topology: str = "hub"
) -> RunResult:
    mcp_servers.reset()  # every run starts from the same data — the company's systems'...
    iam_data.reset()  # ...and the IAM team's
    desk = service_desk(
        session_for(case.user), tools, False, client, topology=topology
    )  # the case's user is already logged in
    # The remote agent's LLM bill is the IAM team's; we add it to ours to compare with module 1 (all in-process).
    remote_calls, remote_cost = access.usage.calls, access.cost()
    start = time.perf_counter()
    replies = []
    for turn in case.turns:
        replies.append(desk.reply(turn))
        # Module 4: the desk may pause for the user's confirmation. The simulated user answers it (at most twice
        # per turn: a desk that keeps asking is a failure the checks will show, not an endless loop).
        for _ in range(2):
            if not desk.awaiting_confirmation:
                break
            replies.append(desk.reply(case.confirm))
    return RunResult(
        replies=replies,
        tool_calls=desk.tool_calls,
        calls=desk.usage.calls + access.usage.calls - remote_calls,
        cost=desk.cost() + access.cost() - remote_cost,
        latency=time.perf_counter() - start,
    )


def run_case_with_retry(
    case: Case,
    access: AccessExecutor,
    client: A2AClient,
    tools: dict[str, Tool],
    topology: str = "hub",
    attempts: int = 3,
) -> RunResult:
    """A network blip or a 5xx/429 from the API says nothing about the agent: retry the whole run (from clean
    data) instead of crashing the eval. Any other exception still crashes on purpose — that's a bug."""
    for attempt in range(1, attempts + 1):
        try:
            return run_case(case, access, client, tools, topology)
        except (
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError,
            openai.RateLimitError,
        ):
            if attempt == attempts:
                raise
            print(
                f"  (case {case.id}: connection error, retrying {attempt}/{attempts - 1})"
            )
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="runs per case (the LLM varies between runs)",
    )
    parser.add_argument("--case", type=int, nargs="*", help="only these case ids")
    parser.add_argument("--topology", choices=("hub", "supervisor"), default="hub")
    args = parser.parse_args()

    cases = [c for c in CASES if not args.case or c.id in args.case]
    rows = []
    # The IAM team's Access agent, served here on a free port — the eval needs nothing else running.
    access = AccessExecutor(
        make_agent=lambda session: access_agent_for(session, verbose=False)
    )
    _, url = start(access)
    client = A2AClient(url)  # discover once for the whole eval
    _, mcp_url = mcp_servers.start()
    tools = mcp_client.connect(mcp_urls(mcp_url))  # also once
    print(
        f"Service Desk ({args.topology} + Access via A2A at {url} + 5 systems via MCP/HTTP at {mcp_url}) | "
        f"{len(cases)} cases x {args.runs} runs\n"
    )
    print(
        f"{'#':>3}  {'category':<9} {'pass':<6} {'calls':>5} {'cost US$':>9} {'time s':>7}  notes"
    )

    for case in cases:
        runs = [
            run_case_with_retry(case, access, client, tools, args.topology) for _ in range(args.runs)
        ]
        failures = [[msg for check in case.checks if (msg := check(r))] for r in runs]
        passed = sum(1 for f in failures if not f)
        row = {
            "id": case.id,
            "category": case.category,
            "turns": case.turns,
            "passed": passed,
            "runs": args.runs,
            "avg_calls": fmean(r.calls for r in runs),
            "avg_cost": fmean(r.cost for r in runs),
            "avg_latency": fmean(r.latency for r in runs),
            # Module 4: how often the desk asked the user to confirm (each one = an extra turn for the user).
            "avg_confirmations": fmean(len(r.replies) - len(case.turns) for r in runs),
            "failures": [f for f in failures if f],
            "replies": [r.replies[-1] for r in runs],  # final reply of each run
            "tools": [[t.name for t in r.tool_calls] for r in runs],
            # Arguments too: without them you can't tell WHY a call failed (e.g. an invented justification).
            "tool_args": [[{t.name: t.arguments} for t in r.tool_calls] for r in runs],
        }
        rows.append(row)

        note = "; ".join(sorted({msg for f in row["failures"] for msg in f}))
        mark = "✅" if passed == args.runs else ("❌" if passed == 0 else "⚠️")
        print(
            f"{case.id:>3}  {case.category:<9} {mark}{passed}/{args.runs:<3} {row['avg_calls']:>5.1f} "
            f"{row['avg_cost']:>9.5f} {row['avg_latency']:>7.1f}  {note}"
        )

    total_runs = sum(r["runs"] for r in rows)
    total_pass = sum(r["passed"] for r in rows)
    summary = {
        "arch": f"{args.topology}-a2a-mcp",
        "pass_rate": total_pass / total_runs if total_runs else 0.0,
        "avg_calls": fmean(r["avg_calls"] for r in rows),
        "avg_cost": fmean(r["avg_cost"] for r in rows),
        "avg_latency": fmean(r["avg_latency"] for r in rows),
        "confirmations": sum(r["avg_confirmations"] * r["runs"] for r in rows),
        "total_cost": sum(r["avg_cost"] * r["runs"] for r in rows),
    }
    print(
        f"\nPass rate: {summary['pass_rate']:.0%} ({total_pass}/{total_runs})"
        f" | avg per case: {summary['avg_calls']:.1f} calls, US$ {summary['avg_cost']:.5f},"
        f" {summary['avg_latency']:.1f}s | confirmations asked: {summary['confirmations']:.0f}"
        f" | eval total: US$ {summary['total_cost']:.4f}"
    )

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{args.topology}-a2a-mcp-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(
        json.dumps({"summary": summary, "cases": rows}, ensure_ascii=False, indent=2)
    )
    print(f"Saved: {out.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
