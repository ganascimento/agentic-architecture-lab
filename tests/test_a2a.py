"""A2A service tests — no LLM: a fake agent stands in for the Access agent (see conftest.py).
Real HTTP, real SDK on both sides: what's tested is OUR behavior on top of the protocol."""

import time

import httpx
import jwt
import pytest
from a2a.client import A2AClientError
from a2a.types import TaskNotFoundError, TaskState
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.identity import SERVICE_ID, _private_key, delegated_token
from src.services.a2a_client import data_of, text_of

SEND = {"jsonrpc": "2.0", "id": "1", "method": "SendMessage",
        "params": {"message": {"messageId": "m1", "role": "ROLE_USER", "parts": [{"text": "preciso de acesso"}]}}}


def _raw_send(client, headers: dict) -> httpx.Response:
    """A hand-made call — what an attacker (or a buggy client) can send, bypassing our A2AClient."""
    return httpx.post(client.card.supported_interfaces[0].url, json=SEND, headers=headers)


def _token(client, key=None, **overrides) -> str:
    now = int(time.time())
    claims = {"iss": SERVICE_ID, "sub": "ana@company.com", "aud": client.card.supported_interfaces[0].url,
              "iat": now, "exp": now + 60} | overrides
    return jwt.encode(claims, key or _private_key(), algorithm="EdDSA")


def test_discovery_reads_the_agent_card(client):
    assert client.card.name == "Access Request Agent"
    assert {s.id for s in client.card.skills} == {"access-request", "access-status"}
    assert client.card.capabilities.streaming  # the SDK gives us SSE — the card advertises it
    # HOW to authenticate is part of the contract too (the SDK's AuthInterceptor reads it).
    assert client.card.security_schemes["delegatedToken"].http_auth_security_scheme.bearer_format == "JWT"


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


# --- Identity between services (lesson 2.5): every one of these is refused BEFORE the protocol runs ---------
def test_no_token_is_401(client):
    assert _raw_send(client, {}).status_code == 401


def test_the_old_naive_header_is_ignored(client):
    # Lesson 2.2's flaw: "x-user-email: carlos@..." made you Carlos. Now a claim without a signature is nothing.
    assert _raw_send(client, {"x-user-email": "carlos@company.com"}).status_code == 401


def test_token_signed_with_another_key_is_401(client):
    # An attacker writes a perfect token claiming to be the Service Desk — but can't sign with ITS private key.
    forged = _token(client, key=Ed25519PrivateKey.generate())
    assert _raw_send(client, {"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_for_another_service_is_401(client):
    # A token the Service Desk made for some OTHER agent can't be replayed here (aud = that agent's URL).
    token = delegated_token("ana@company.com", audience="http://localhost:9999/a2a")
    assert _raw_send(client, {"Authorization": f"Bearer {token}"}).status_code == 401


def test_expired_token_is_401(client):
    old = _token(client, iat=int(time.time()) - 120, exp=int(time.time()) - 60)
    assert _raw_send(client, {"Authorization": f"Bearer {old}"}).status_code == 401


def test_untrusted_caller_is_401(client):
    # Signed by us, but claiming to be a service IAM never registered: the issuer must be in THEIR trust list.
    token = _token(client, iss="rogue-service")
    assert _raw_send(client, {"Authorization": f"Bearer {token}"}).status_code == 401


def test_unknown_user_is_401(client):
    with pytest.raises(A2AClientError, match="401"):
        client.send("preciso de acesso", user_email="nobody@company.com")


def test_the_service_desk_is_trusted_for_any_user(client):
    # ⚠️ The trust boundary that REMAINS (documented, not a bug): IAM believes any `sub` the Service Desk signs.
    # A compromised Service Desk can act as anyone. Fix: an IdP doing token exchange from the USER's own token
    # (final phase, with real user authentication). What 2.5 removed: ANYONE ELSE acting as anyone.
    task = client.send("preciso de acesso, justificativa: fechamento", user_email="carlos@company.com")
    assert "carlos@company.com" in text_of(task)


def test_someone_elses_task_is_not_found(client):
    # IDOR on the protocol: Carlos knows Ana's task id — that's not permission to continue it. The SDK's task store
    # is scoped by the VERIFIED user (from the token): to Carlos, Ana's task doesn't exist.
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
