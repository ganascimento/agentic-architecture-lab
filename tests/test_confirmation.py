"""Human-in-the-loop with the user (lesson 4.4) — no LLM: the catalog agent's run() is scripted.

The script plays the LLM's part: 1st activation → asks for request_catalog_approval with the given justification;
any later activation → reports whatever the code told it (the last system note). Everything else is real: the
graph, the interrupt, the MCP catalog server, the provenance checks."""

import pytest

from src import conversations
from src.architectures import confirm, service_desk
from src.architectures.confirm import CONFIRM_ASKED
from src.auth import session_for
from src.services.mcp_servers.catalog import data as catalog

ANA = session_for("ana@company.com")
INVENTED = "Solicita Adobe Acrobat Pro (instalação de software novo)."  # eval case 42: passes check() at 50%


def _catalog_desk(client, systems, justification: str, checkpointer=None, runs: list | None = None):
    desk = service_desk(ANA, systems, False, client, checkpointer, "ana/1")
    if not desk.state:  # a fresh thread (a restored one already knows who's active — and is paused)
        desk.graph.update_state(desk.config, {"active": "catalog"})
    agent = desk.agents["catalog"]
    runs = [] if runs is None else runs

    def run() -> str:
        runs.append(agent.messages[-1]["content"])
        if len(runs) == 1:
            arguments = {"item_id": "SW004", "justification": justification}
            if agent.intercept("request_catalog_approval", arguments) == (CONFIRM_ASKED, True):
                return ""
            agent._run_tool("request_catalog_approval", arguments)  # not held: the loop runs it as usual
            return "ran without asking"
        return f"report: {agent.messages[-1]['content']}"
    agent.run = run
    return desk, runs


def _requests() -> list[dict]:
    return [r for r in catalog.CATALOG_REQUESTS.values() if r["email"] == ANA.email]


def test_probably_the_users_words_are_shown_to_the_user_first(client, systems):
    desk, _ = _catalog_desk(client, systems, INVENTED)
    before = len(_requests())
    reply = desk.reply("quero o Adobe Acrobat Pro")
    assert desk.awaiting_confirmation and INVENTED in reply  # the user sees the EXACT text the code would send
    assert len(_requests()) == before  # nothing ran yet


def test_yes_runs_the_call_once_and_the_agent_reports_it(client, systems):
    desk, runs = _catalog_desk(client, systems, INVENTED)
    before = len(_requests())
    desk.reply("quero o Adobe Acrobat Pro")
    reply = desk.reply("sim")
    assert not desk.awaiting_confirmation and len(_requests()) == before + 1
    assert [c.name for c in desk.tool_calls] == ["request_catalog_approval"] and not desk.tool_calls[0].is_error
    # The catalog agent ran TWICE (ask, report), not three times: resuming re-ran only the confirm node.
    assert len(runs) == 2 and "confirmed" in reply


def test_any_other_answer_goes_back_to_the_agent_as_the_users_message(client, systems):
    desk, runs = _catalog_desk(client, systems, INVENTED)
    before = len(_requests())
    desk.reply("quero o Adobe Acrobat Pro")
    desk.reply("sim, mas o motivo é editar os contratos do jurídico")  # a "yes" with a correction is not a yes
    assert len(_requests()) == before and desk.tool_calls == []
    assert "did NOT confirm" in runs[-1]
    assert desk.state["messages"][-2]["content"] == "sim, mas o motivo é editar os contratos do jurídico"


def test_the_users_own_words_run_without_asking(client, systems):
    desk, _ = _catalog_desk(client, systems, "para editar os contratos do jurídico")
    desk.reply("quero o Adobe Acrobat Pro para editar os contratos do jurídico")
    assert not desk.awaiting_confirmation and desk.tool_calls[0].name == "request_catalog_approval"


def test_clearly_invented_words_are_still_refused_not_asked(client, systems):
    # Below 50% nothing changes: run_tool refuses and the LLM must ask the user (module 1's rule).
    desk, _ = _catalog_desk(client, systems, "Necessário para a auditoria trimestral de compliance.")
    desk.reply("quero o Adobe Acrobat Pro")
    assert not desk.awaiting_confirmation and desk.tool_calls[0].is_error


def test_a_paused_confirmation_survives_a_restart(client, systems, tmp_path):
    store = conversations.open_store(tmp_path / "desk.sqlite")
    before = len(_requests())
    desk, _ = _catalog_desk(client, systems, INVENTED, store)
    desk.reply("quero o Adobe Acrobat Pro")
    restarted, _ = _catalog_desk(client, systems, INVENTED, store, runs=["(before the restart)"])
    assert restarted.awaiting_confirmation  # the pause is in the checkpoint, not in a waiting process
    restarted.reply("sim")
    assert len(_requests()) == before + 1


def test_force_new_is_the_users_decision_not_the_llms():
    tool = type("T", (), {"name": "open_ticket", "from_user": ()})()
    assert confirm.prompt_for(tool, {"title": "Outlook", "force_new": True}, []) is not None
    assert confirm.prompt_for(tool, {"title": "Outlook"}, []) is None


@pytest.mark.parametrize("answer, expected", [
    ("sim", True), ("Sim!", True), ("ok, pode registrar", True), ("yes", True),
    ("não", False), ("sim, mas o motivo é outro", False), ("talvez", False), ("", False),
])
def test_only_a_plain_yes_confirms(answer, expected):
    assert confirm.is_yes(answer) is expected
