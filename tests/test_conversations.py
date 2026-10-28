"""Saved conversations (lesson 4.3) — no LLM: the agents' run() is replaced by fixed answers.

A "restart" here = a NEW desk object (new agents, new clients, nothing in memory) on the SAME SQLite file and
thread id. Whatever it still knows came from the checkpoint."""

import pytest

from src import conversations
from src.architectures import service_desk
from src.auth import session_for

ANA, BRUNO = session_for("ana@company.com"), session_for("bruno@company.com")


@pytest.fixture
def store(tmp_path):
    return conversations.open_store(tmp_path / "desk.sqlite")


def _desk(client, systems, store, session=ANA, number=1):
    return service_desk(session, systems, False, client, store, conversations.thread_id(session, number))


def _scripted(desk):
    """Hub hands anything about a printer to support; support answers with how many user messages it saw."""
    hub, support = desk.agents["triage"], desk.agents["support"]
    hub.run = lambda: hub.intercept("transfer_to_support", {"reason": "printer"}) and ""
    support.run = lambda: f"support saw {sum(m['role'] == 'user' for m in support.messages)} user messages"
    return desk


def test_the_conversation_survives_a_restart(client, systems, store):
    before = _scripted(_desk(client, systems, store))
    before.reply("a impressora está borrada")
    after = _scripted(_desk(client, systems, store))  # "restart": new objects, same file + thread
    assert after.active == "support"  # who was talking to the user came back from the checkpoint
    assert after.reply("continua borrada") == "support saw 2 user messages"  # it got the whole conversation


def test_a_remote_task_waiting_for_the_user_survives_a_restart(client, systems, store):
    # The A2A task id is a POINTER into the IAM service: state, so it's in the checkpoint too.
    before = _desk(client, systems, store)
    before.graph.update_state(before.config, {"active": "access"})
    before.reply("preciso de acesso à pasta Financeiro")  # the remote asks for the justification
    after = _desk(client, systems, store)
    after.agents["triage"].run = lambda: ""
    assert "REQ0002" in after.reply("é para o fechamento")  # answered the SAME remote task


def test_a_user_only_sees_their_own_threads(client, systems, store):
    for session, number in ((ANA, 1), (ANA, 2), (BRUNO, 1)):
        desk = _desk(client, systems, store, session, number)
        desk.agents["triage"].run = lambda: "Hi!"
        desk.reply("oi")
    assert conversations.threads_of(store, ANA) == [1, 2]
    assert conversations.threads_of(store, BRUNO) == [1]
    # The id is built from the session: there's no input that makes Ana's "/open 1" reach Bruno's thread.
    assert conversations.thread_id(ANA, 1) != conversations.thread_id(BRUNO, 1)


def test_undo_forgets_the_last_turn_but_the_history_keeps_it(client, systems, store):
    desk = _scripted(_desk(client, systems, store))
    desk.reply("a impressora está borrada")
    desk.reply("e agora está manchando")
    steps = len(desk.history())
    assert desk.undo() is True
    assert desk.reply("na verdade está falhando") == "support saw 2 user messages"  # turn 2 is gone for the agents
    assert len(desk.history()) > steps  # the old branch is still in the checkpointer (audit)


def test_the_first_turn_cannot_be_undone(client, systems, store):
    desk = _scripted(_desk(client, systems, store))
    desk.reply("a impressora está borrada")
    assert desk.undo() is False  # there's no "before": /new starts another conversation


def test_a_saved_remote_task_that_no_longer_exists_starts_a_new_one(client, systems, store):
    # The IAM service restarted (its tasks live in memory): the task id in OUR checkpoint points to nothing.
    desk = _desk(client, systems, store)
    desk.agents["triage"].run = lambda: ""
    desk.graph.update_state(desk.config, {"active": "access", "remote_task": "lost-in-a-restart"})
    assert "REQ0002" in desk.reply("preciso de acesso, justificativa: fechamento")  # no crash: a fresh task
