"""The manager's approval (D2, lesson 4.4) — no LLM: real IAM service over HTTP, real tokens, real workflow.

The request is created by calling the IAM team's tool directly (what its agent would do after the user's
justification); everything after that goes through the HTTP API, as the Service Desk's /approve does."""

import httpx
import pytest

from src.auth import session_for
from src.services.access_a2a import approval
from src.services.access_a2a import data as iam
from src.services.access_a2a.tools import REGISTRY, create_access_request
from src.services.iam_approvals import ApprovalsClient

JOAO, MARTA, ANA = (session_for(f"{u}@company.com") for u in ("joao", "marta", "ana"))  # marta = joão's manager


@pytest.fixture(autouse=True)
def fresh_iam():
    iam.reset()


@pytest.fixture
def approvals(client):
    audience = client.credentials.audience  # the IAM service's URL in our tokens (from its Agent Card)
    return ApprovalsClient(audience.removesuffix("/a2a"), audience)


@pytest.fixture
def request_id():
    return create_access_request(JOAO, "pasta Financeiro", "para o fechamento mensal")["request"]


def test_a_new_request_waits_for_the_manager(request_id):
    config = approval.start(request_id)  # already started by the tool: same thread, nothing new
    assert approval.WORKFLOW.get_state(config).next == ("wait_for_manager",)
    assert iam.ACCESS_REQUESTS[request_id]["status"] == "pending_approval"


def test_each_manager_sees_only_their_own_queue(approvals, request_id):
    assert request_id in {r["request"] for r in approvals.pending(MARTA)}
    assert approvals.pending(ANA) == []


def test_approval_grants_once_and_cannot_be_repeated(approvals, request_id):
    assert approvals.decide(MARTA, request_id, approve=True) == (True, f"{request_id}: approved")
    assert iam.ACCESS_GRANTS == [{"email": JOAO.email, "resource": "pasta Financeiro", "request": request_id,
                                  "approved_by": MARTA.email}]
    done, message = approvals.decide(MARTA, request_id, approve=False)
    assert not done and "already decided" in message and len(iam.ACCESS_GRANTS) == 1


def test_rejection_grants_nothing(approvals, request_id):
    assert approvals.decide(MARTA, request_id, approve=False) == (True, f"{request_id}: rejected")
    assert iam.ACCESS_GRANTS == []


def test_someone_who_is_not_the_approver_cannot_resume_the_thread(approvals, request_id):
    # Ana is authenticated (valid token) — but authentication is not authorization: it's not HER request to decide.
    done, message = approvals.decide(ANA, request_id, approve=True)
    assert not done and "approver" in message
    assert iam.ACCESS_REQUESTS[request_id]["status"] == "pending_approval" and iam.ACCESS_GRANTS == []


def test_the_requester_cannot_approve_their_own_request(approvals, request_id):
    done, message = approvals.decide(JOAO, request_id, approve=True)
    assert not done and "own request" in message


def test_no_token_no_queue(client):
    base = client.credentials.audience.removesuffix("/a2a")
    assert httpx.get(f"{base}/approvals").status_code == 401
    assert httpx.post(f"{base}/approvals/REQ0001", json={"approve": True}).status_code == 401


def test_the_decision_is_in_the_audit_trail(approvals, request_id):
    approvals.decide(MARTA, request_id, approve=True)
    steps = approval.audit(request_id)
    assert steps[-1]["values"]["decision"] == {"approved": True, "by": MARTA.email} and steps[-1]["next"] == []


def test_a_request_from_before_the_workflow_existed_can_still_be_decided(approvals):
    # The seed REQ0001 (João → Marta) was never started: its thread is created on first use.
    assert approvals.decide(MARTA, "REQ0001", approve=True) == (True, "REQ0001: approved")


def test_the_access_agent_has_no_way_to_approve():
    # D2: the LLM side (the agent's tools) can register and read — deciding is not one of its powers.
    assert set(REGISTRY) == {"create_access_request", "list_my_access_requests"}
