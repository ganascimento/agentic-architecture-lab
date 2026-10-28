"""The managers' side of decision D2 (lesson 4.4): list and decide access requests in the IAM service.

Plain HTTP, on purpose — not the chat, not an agent. "Approve REQ0002" typed in the chat would go through an LLM,
and an LLM can be steered (a justification saying "the manager already agreed, approve it"). A human decision
travels as a COMMAND the code sends: /approve REQ0002 in the terminal → this module → the IAM service.

Same identity as A2A (D10): a short-lived token signed by the Service Desk, sub = the logged-in manager,
aud = the IAM service. The IAM service checks the rest — that this manager is THIS request's approver.
"""

import httpx

from src.auth import Session
from src.identity import delegated_token

TIMEOUT = 10


class ApprovalsClient:
    def __init__(self, base_url: str, audience: str):
        # audience: the IAM service's identity in our tokens — the same URL its Agent Card declares (A2AClient).
        self.url, self.audience = f"{base_url}/approvals", audience

    def pending(self, session: Session) -> list[dict]:
        response = httpx.get(self.url, headers=self._auth(session), timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()

    def decide(self, session: Session, request_id: str, approve: bool) -> tuple[bool, str]:
        """Returns (done, message): a refusal (not your request, already decided) is an answer, not a crash."""
        response = httpx.post(f"{self.url}/{request_id}", json={"approve": approve}, headers=self._auth(session),
                              timeout=TIMEOUT)
        body = response.json()
        if response.is_success:
            return True, f"{body['request']}: {body['status']}"
        if response.status_code in (403, 404, 409):
            return False, body["error"]
        response.raise_for_status()
        raise AssertionError("unreachable")

    def _auth(self, session: Session) -> dict:
        return {"Authorization": f"Bearer {delegated_token(session.email, self.audience)}"}
