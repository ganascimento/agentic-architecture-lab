"""A2A service tests — no LLM: a fake agent stands in for the Access agent (see conftest.py)."""

import pytest

from src.services.a2a_protocol import data_of, text_of


def test_discovery_reads_the_agent_card(client):
    assert client.card["name"] == "Access Request Agent"
    assert {s["id"] for s in client.card["skills"]} == {"access-request", "access-status"}


def test_task_goes_input_required_then_completed(client):
    task = client.send("preciso de acesso à pasta Financeiro", user_email="ana@company.com")
    assert task["status"]["state"] == "TASK_STATE_INPUT_REQUIRED"
    assert "justification" in text_of(task)
    # Same task, continued: the client (not the remote agent) got the answer from the user.
    done = client.send("é para o fechamento", user_email="ana@company.com",
                       task_id=task["id"], context_id=task["contextId"])
    assert done["id"] == task["id"] and done["status"]["state"] == "TASK_STATE_COMPLETED"
    assert "REQ0002" in text_of(done)
    # Text for the human AND data for the machine: the caller doesn't parse prose to know what happened.
    assert data_of(done) == {"accessRequest": {"request": "REQ0002"}}


def test_a_reply_without_ask_user_completes_the_task(client):
    # The old bug: "no tool ran = it's asking" left this task INPUT_REQUIRED forever — the user's conversation
    # was trapped in the remote agent. Now INPUT_REQUIRED needs the explicit signal (ask_user); default COMPLETED.
    task = client.send("preciso de acesso à pasta Financeiro", user_email="ana@company.com")
    done = client.send("deixa pra lá, minha VPN caiu", user_email="ana@company.com",
                       task_id=task["id"], context_id=task["contextId"])
    assert done["status"]["state"] == "TASK_STATE_COMPLETED"
    assert data_of(done) == {}  # nothing was registered: no data part


def test_unknown_task_is_a_jsonrpc_error(client):
    with pytest.raises(RuntimeError, match="-32001"):
        client.send("oi", user_email="ana@company.com", task_id="does-not-exist")


def test_naive_identity_is_forgeable(client):
    # ⚠️ Documents the flaw fixed in lesson 2.5: the caller just SAYS who the user is, and the server believes it.
    task = client.send("preciso de acesso, justificativa: fechamento", user_email="carlos@company.com")
    assert "carlos@company.com" in text_of(task)


def test_someone_elses_task_is_not_found(client):
    # IDOR on the protocol: Carlos knows Ana's task and context ids — that's not permission to continue it.
    task = client.send("preciso de acesso à pasta Financeiro", user_email="ana@company.com")
    with pytest.raises(RuntimeError, match="-32001"):
        client.send("é para o fechamento", user_email="carlos@company.com",
                    task_id=task["id"], context_id=task["contextId"])
