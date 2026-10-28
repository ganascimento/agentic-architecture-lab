"""The supervisor topology (lesson 4.5) — no LLM: the agents' run() is scripted, the graph is real.

The scripted supervisor delegates on its 1st activation and, on the next one, "combines" by echoing the
specialists' answers it was given — so the tests see exactly what reached it."""

from src.architectures import service_desk, supervisor
from src.auth import session_for

ANA = session_for("ana@company.com")


def _desk(client, systems):
    return service_desk(ANA, systems, False, client, topology="supervisor")


def _script_supervisor(desk, *delegations: tuple[str, str]):
    boss = desk.agents["supervisor"]

    def run() -> str:
        last = boss.messages[-1]["content"]
        if last.startswith("[specialists' answers]"):
            return f"combined: {last}"
        for name, task in delegations:
            boss.intercept(f"ask_{name}", {"task": task})
        return ""
    boss.run = run
    return boss


def test_the_supervisor_only_has_specialists_as_tools(client, systems):
    desk = _desk(client, systems)
    assert desk.agents["supervisor"].allowed_tools == {"ask_support", "ask_account", "ask_catalog", "ask_access"}
    # The specialists keep their least privilege — and have no transfer tools: they never talk to the user.
    assert not any(t.startswith("transfer_to_") for a in ("support", "account", "catalog")
                   for t in desk.agents[a].allowed_tools)
    assert "request_password_reset" not in desk.agents["support"].allowed_tools


def test_specialists_run_in_parallel_and_the_supervisor_combines(client, systems):
    desk = _desk(client, systems)
    _script_supervisor(desk, ("support", "blurry printer"), ("catalog", "a headset"))
    seen = {}
    for name in ("support", "catalog"):
        agent = desk.agents[name]
        agent.run = (lambda a=agent, n=name: seen.setdefault(n, a.messages[-1]["content"]) and f"{n} done")
    reply = desk.reply("a impressora está borrada e preciso de um headset")
    assert "support done" in reply and "catalog done" in reply  # ONE reply with both answers
    assert seen == {"support": "[task from the supervisor] blurry printer",
                    "catalog": "[task from the supervisor] a headset"}
    # Both workers ran in the SAME step (a map): the checkpoint before it had two pending "worker" tasks.
    assert any(snap.next == ("worker", "worker") for snap in desk.graph.get_state_history(desk.config))


def test_two_tasks_for_the_same_specialist_become_one(client, systems):
    desk = _desk(client, systems)
    jobs: dict = {}
    desk._delegate(jobs, 0, "ask_support", {"task": "blurry printer"})
    desk._delegate(jobs, 0, "ask_support", {"task": "outlook crashing"})
    assert jobs == {"support": "blurry printer Also: outlook crashing"}


def test_the_code_stops_a_delegation_loop(client, systems):
    desk = _desk(client, systems)
    jobs: dict = {}
    result, end_turn = desk._delegate(jobs, supervisor.MAX_ROUNDS, "ask_support", {"task": "again"})
    assert result == supervisor.NO_MORE_ROUNDS and end_turn is False and jobs == {}


def test_a_new_turn_starts_with_no_answers(client, systems):
    # The `results` reducer resets on None (the turn's input): last turn's answers don't leak into this one.
    desk = _desk(client, systems)
    _script_supervisor(desk, ("account", "reset my password"))
    desk.agents["account"].run = lambda: "reset link sent"
    desk.reply("esqueci minha senha")
    desk.agents["supervisor"].run = lambda: "Bye!"
    desk.reply("valeu")
    assert desk.state["results"] == []


def test_the_remote_specialist_is_one_more_worker(client, systems):
    desk = _desk(client, systems)
    _script_supervisor(desk, ("access", "access to the Finance folder"))
    reply = desk.reply("preciso de acesso à pasta Financeiro")
    assert "What is the justification?" in reply  # the fake IAM agent's question, relayed by the supervisor
    assert desk.state["remote_task"] is not None  # the open A2A task is state: the next turn continues it


def test_a_held_call_is_confirmed_by_the_user_before_it_runs(client, systems):
    desk = _desk(client, systems)
    _script_supervisor(desk, ("catalog", "Adobe Acrobat Pro"))
    catalog = desk.agents["catalog"]
    arguments = {"item_id": "SW004", "justification": "Solicita Adobe Acrobat Pro (instalação de software novo)."}
    catalog.run = lambda: catalog.intercept("request_catalog_approval", arguments) and ""
    reply = desk.reply("quero o Adobe Acrobat Pro")
    assert desk.awaiting_confirmation and "instalação de software novo" in reply and desk.tool_calls == []
    final = desk.reply("sim")
    assert [c.name for c in desk.tool_calls] == ["request_catalog_approval"] and not desk.tool_calls[0].is_error
    assert "confirmed" in final  # the outcome went back to the supervisor as the catalog's answer
