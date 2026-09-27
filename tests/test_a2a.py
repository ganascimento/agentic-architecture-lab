"""A2A service tests — no LLM: a fake agent stands in for the Access agent, a real HTTP server runs on a free port."""

import threading
from http.server import ThreadingHTTPServer

import pytest

from src.core.agent import ToolCall
from src.services.a2a_client import A2AClient, text_of
from src.services.access_a2a.server import AccessA2AService, make_handler


class FakeAccessAgent:
    """Asks for the justification first, then 'registers' the request — like the real one, without an LLM."""

    def __init__(self, session):
        self.session, self.tool_calls = session, []

    def reply(self, text: str) -> str:
        if "justific" in text or "fechamento" in text:
            self.tool_calls.append(ToolCall("create_access_request", {}, '{"request": "REQ0002"}', False))
            return f"Registered REQ0002 for {self.session.email}"
        return "What is the justification?"


@pytest.fixture
def client():
    server = ThreadingHTTPServer(("localhost", 0), make_handler(AccessA2AService(make_agent=FakeAccessAgent)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield A2AClient(f"http://localhost:{server.server_port}")
    server.shutdown()


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


def test_unknown_task_is_a_jsonrpc_error(client):
    with pytest.raises(RuntimeError, match="-32001"):
        client.send("oi", user_email="ana@company.com", task_id="does-not-exist")


def test_naive_identity_is_forgeable(client):
    # ⚠️ Documents the flaw fixed in lesson 2.5: the caller just SAYS who the user is, and the server believes it.
    task = client.send("preciso de acesso, justificativa: fechamento", user_email="carlos@company.com")
    assert "carlos@company.com" in text_of(task)
