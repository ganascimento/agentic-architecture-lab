"""The IAM team's tools: access requests. Decision D2: the agent only REGISTERS; granting happens elsewhere,
after human approval. They run INSIDE the service — the Service Desk never sees them (opaque agent)."""

from src import data  # the company directory (shared infra): who is whose manager
from src.auth import Session
from src.services.access_a2a import data as iam
from src.tools._schema import NO_ARGS, Tool, definition


def create_access_request(session: Session, resource: str, justification: str) -> dict:
    # The justification was already checked by run_tool (from_user below): not empty, not just the request
    # restated, and mostly the user's own words. This function only runs if it passed.
    approver = data.USERS[session.email]["manager"]  # looked up by code, not chosen by the LLM
    request_id = f"REQ{len(iam.ACCESS_REQUESTS) + 1:04d}"
    iam.ACCESS_REQUESTS[request_id] = {
        "email": session.email, "resource": resource, "justification": justification,
        "approver": approver, "status": "pending_approval",
    }
    return {"request": request_id, "status": "pending_approval", "approver": approver}


def list_my_access_requests(session: Session) -> list[dict]:
    return [
        {"request": rid, "resource": r["resource"], "status": r["status"], "approver": r["approver"]}
        for rid, r in iam.ACCESS_REQUESTS.items() if r["email"] == session.email
    ]


TOOLS = [
    Tool(definition(
        "create_access_request",
        "Registers an access request for a folder or system for the logged-in user. It does NOT grant access: "
        "the request stays pending until the manager approves it. For the justification, use the reason the user "
        "gave in their own words (e.g. 'for the monthly closing'); only if they gave no reason at all, ask for it.",
        {
            "type": "object",
            "properties": {
                "resource": {"type": "string", "description": "Folder or system, e.g. 'Finance folder'"},
                "justification": {"type": "string"},
            },
            "required": ["resource", "justification"],
        },
    ), create_access_request, from_user=("justification",)),
    Tool(definition(
        "list_my_access_requests", "Lists the logged-in user's access requests and their status.", NO_ARGS,
    ), list_my_access_requests),
]

REGISTRY = {t.name: t for t in TOOLS}
