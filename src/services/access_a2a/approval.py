"""The manager's approval of an access request (decision D2) as a durable workflow — lesson 4.4.

D2 since module 1: the LLM only REGISTERS a request; a human approves; CODE executes. Until module 4 the middle
part didn't exist: every request stayed `pending_approval` forever. Now each request starts a small graph:

    START → wait_for_manager ──interrupt()── … days … ──resume(decision)──→ apply_decision → END

- The pause is a CHECKPOINT, not a waiting process: nothing runs while the manager thinks.
- There is NO LLM in this graph. The decision arrives through an authenticated HTTP call (server.py), made by the
  approver — not through a chat that a prompt injection could steer.
- WHO may resume is checked BEFORE resuming (decide): the request's approver, never the requester. A thread id
  is a pointer, not a permission (lesson 4.1, section 9) — LangGraph resumes whatever thread you name.
- The side effect (the grant) is in its own node, AFTER the interrupt: on resume the waiting node re-runs from
  its first line, so nothing with effects may come before interrupt() (lesson 4.1, section 5).

Honest note (lesson 4.1, question 5): for ONE approval, a status column + an endpoint does the same. The graph
earns its place as the process grows — a second approver for sensitive resources, a reminder when nobody decides
in N days, provisioning that fails and must resume — each a node, every wait durable.

Where the checkpoints live: in MEMORY, like the IAM data itself (data.py). Saving one durably and not the other
would make them disagree after a crash (an approval thread for a request that no longer exists). In production
both go to the same database — ideally in the same transaction.
"""

import threading
import uuid
from typing import NotRequired, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from src.services.access_a2a import data as iam


class ApprovalState(TypedDict):
    request: str  # the request id (the data itself stays in iam.ACCESS_REQUESTS: one source of truth)
    decision: NotRequired[dict]  # {"approved": bool, "by": approver email} — what the manager answered


def _wait_for_manager(state: ApprovalState) -> dict:
    # Nothing before this line: it runs again on resume.
    return {"decision": interrupt({"request": state["request"]})}


def _apply_decision(state: ApprovalState) -> dict:
    """The CODE executes the human's decision (D2) — once, after the pause."""
    request, decision = iam.ACCESS_REQUESTS[state["request"]], state["decision"]
    request["status"] = "approved" if decision["approved"] else "rejected"
    request["decided_by"] = decision["by"]
    if decision["approved"]:
        # Stands in for the real provisioning (an AD group, a SAP role...). A failure here would leave the thread
        # at this node — retrying it later is exactly what a durable workflow is for.
        iam.ACCESS_GRANTS.append({"email": request["email"], "resource": request["resource"],
                                  "request": state["request"], "approved_by": decision["by"]})
    return {}


def _build() -> CompiledStateGraph:
    graph = StateGraph(ApprovalState)
    graph.add_node("wait_for_manager", _wait_for_manager)
    graph.add_node("apply_decision", _apply_decision)
    graph.add_edge(START, "wait_for_manager")
    graph.add_edge("wait_for_manager", "apply_decision")
    graph.add_edge("apply_decision", END)
    return graph.compile(checkpointer=InMemorySaver())


WORKFLOW = _build()
# Check-then-resume must be atomic: two clicks on "approve" would both see the pause and both resume. A lock is
# enough in one process; with several instances it's the database's job (a row lock, a unique constraint).
_LOCK = threading.Lock()


def start(request_id: str) -> RunnableConfig:
    """The request's approval thread: created (and paused at the manager) on first use. The thread id carries a
    random part, so a request id reused after a data reset never lands on an old, already-decided thread."""
    request = iam.ACCESS_REQUESTS[request_id]
    if "workflow" not in request:
        request["workflow"] = f"approval/{request_id}/{uuid.uuid4().hex[:8]}"
        WORKFLOW.invoke({"request": request_id}, _config(request))
    return _config(request)


def pending_for(approver: str) -> list[dict]:
    """What waits for THIS approver — nobody else's queue."""
    return [
        {"request": rid, "requester": r["email"], "resource": r["resource"], "justification": r["justification"]}
        for rid, r in iam.ACCESS_REQUESTS.items()
        if r["approver"] == approver and r["status"] == "pending_approval"
    ]


def decide(request_id: str, approver: str, approve: bool) -> dict:
    """Resumes the paused thread with the decision — after checking who is deciding (D5: a rule in CODE)."""
    request_id = request_id.upper()
    request = iam.ACCESS_REQUESTS.get(request_id)
    if request is None:
        raise LookupError(f"No access request {request_id}")
    if approver == request["email"]:
        raise PermissionError("Nobody approves their own request")
    if approver != request["approver"]:
        raise PermissionError(f"Only the request's approver can decide {request_id}")
    with _LOCK:
        config = start(request_id)
        if not WORKFLOW.get_state(config).interrupts:
            raise ValueError(f"{request_id} was already decided ({request['status']})")
        WORKFLOW.invoke(Command(resume={"approved": approve, "by": approver}), config)
    return {"request": request_id, "status": request["status"]}


def audit(request_id: str) -> list[dict]:
    """Every saved step of the request's approval, oldest first — who decided what is in the checkpoints."""
    request = iam.ACCESS_REQUESTS[request_id.upper()]
    if "workflow" not in request:
        return []
    return [{"step": (s.metadata or {}).get("step"), "next": list(s.next), "values": s.values}
            for s in reversed(list(WORKFLOW.get_state_history(_config(request))))]


def _config(request: dict) -> RunnableConfig:
    return {"configurable": {"thread_id": request["workflow"]}}
