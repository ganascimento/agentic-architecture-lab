"""A2A service tests — no LLM: a fake agent stands in for the Access agent (see conftest.py).
Real HTTP, real SDK on both sides: what's tested is OUR behavior on top of the protocol."""

import pytest
from a2a.types import InvalidParamsError, TaskNotFoundError, TaskState

from src.services.a2a_client import data_of, text_of


def test_discovery_reads_the_agent_card(client):
    assert client.card.name == "Access Request Agent"
    assert {s.id for s in client.card.skills} == {"access-request", "access-status"}
    assert client.card.capabilities.streaming  # the SDK gives us SSE — the card advertises it


def test_task_goes_input_required_then_completed(client):
    task = client.send("preciso de acesso à pasta Financeiro", user_email="ana@company.com")
    assert task.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
    assert "justification" in text_of(task)
    # Same task, continued: the client (not the remote agent) got the answer from the user.
    done = client.send("é para o fechamento", user_email="ana@company.com",
                       task_id=task.id, context_id=task.context_id)
    assert done.id == task.id and done.status.state == TaskState.TASK_STATE_COMPLETED
    assert "REQ0002" in text_of(done)
    # Text for the human AND data for the machine: the caller doesn't parse prose to know what happened.
    assert data_of(done) == {"accessRequest": {"request": "REQ0002"}}


def test_streaming_reports_progress_before_the_answer(client):
    progress: list[str] = []
    client.send("preciso de acesso à pasta Financeiro", user_email="ana@company.com", on_progress=progress.append)
    assert progress == ["Checking your request..."]  # WORKING arrived as an event, before the final state


def test_a_reply_without_ask_user_completes_the_task(client):
    # The old bug: "no tool ran = it's asking" left this task INPUT_REQUIRED forever — the user's conversation
    # was trapped in the remote agent. Now INPUT_REQUIRED needs the explicit signal (ask_user); default COMPLETED.
    task = client.send("preciso de acesso à pasta Financeiro", user_email="ana@company.com")
    done = client.send("deixa pra lá, minha VPN caiu", user_email="ana@company.com",
                       task_id=task.id, context_id=task.context_id)
    assert done.status.state == TaskState.TASK_STATE_COMPLETED
    assert data_of(done) == {}  # nothing was registered: no data part


def test_unknown_task_is_an_error(client):
    with pytest.raises(TaskNotFoundError):  # a typed error (-32001 on the wire), not a string to parse
        client.send("oi", user_email="ana@company.com", task_id="does-not-exist")


def test_unknown_user_is_an_error(client):
    with pytest.raises(InvalidParamsError, match="Unknown user"):
        client.send("preciso de acesso", user_email="nobody@company.com")


def test_naive_identity_is_forgeable(client):
    # ⚠️ Documents the flaw fixed in lesson 2.5: the caller just SAYS who the user is (a header), and we believe it.
    task = client.send("preciso de acesso, justificativa: fechamento", user_email="carlos@company.com")
    assert "carlos@company.com" in text_of(task)


def test_someone_elses_task_is_not_found(client):
    # IDOR on the protocol: Carlos knows Ana's task id — that's not permission to continue it. The SDK's task store
    # is scoped by user (our NaiveIdentity says who): to Carlos, Ana's task doesn't exist.
    task = client.send("preciso de acesso à pasta Financeiro", user_email="ana@company.com")
    with pytest.raises(TaskNotFoundError):
        client.send("é para o fechamento", user_email="carlos@company.com", task_id=task.id,
                    context_id=task.context_id)


def test_someone_elses_context_opens_a_fresh_conversation(client, service):
    # The contextId is OURS to protect (the SDK stores tasks, not the agent's memory): keyed by (user, context),
    # Carlos reusing Ana's contextId gets a new conversation of his own — never Ana's history.
    task = client.send("preciso de acesso à pasta Financeiro", user_email="ana@company.com")
    client.send("preciso de acesso ao SAP", user_email="carlos@company.com", context_id=task.context_id)
    ana, carlos = (service.agents[(email, task.context_id)] for email in ("ana@company.com", "carlos@company.com"))
    assert ana is not carlos and carlos.messages == ["preciso de acesso ao SAP"]
