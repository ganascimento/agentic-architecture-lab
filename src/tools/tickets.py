"""Ticketing system. Every read/write is scoped to the logged-in user by CODE."""

from src import data
from src.auth import Session
from src.tools._schema import NO_ARGS, Tool, definition


def _own_ticket(session: Session, ticket_id: str) -> dict:
    """Ownership check against IDOR (Insecure Direct Object Reference): knowing an ID is not permission.
    Same error for "doesn't exist" and "not yours" — otherwise the error itself leaks that the ticket exists."""
    ticket = data.TICKETS.get(ticket_id.upper())
    if ticket is None or ticket["email"] != session.email:
        raise ValueError(f"Ticket {ticket_id} not found among your tickets.")
    return ticket


def open_ticket(session: Session, title: str, description: str, category: str, priority: str) -> dict:
    ticket_id = f"INC{len(data.TICKETS) + 1:04d}"
    data.TICKETS[ticket_id] = {
        "email": session.email, "title": title, "description": description,
        "category": category, "priority": priority, "status": "open", "comments": [],
    }
    return {"ticket": ticket_id, "status": "open", "queue": "L2"}


def list_my_tickets(session: Session) -> list[dict]:
    return [
        {"ticket": tid, "title": t["title"], "status": t["status"]}
        for tid, t in data.TICKETS.items() if t["email"] == session.email
    ]


def get_ticket_status(session: Session, ticket_id: str) -> dict:
    t = _own_ticket(session, ticket_id)
    return {"ticket": ticket_id.upper(), "title": t["title"], "status": t["status"], "comments": t["comments"]}


def add_ticket_comment(session: Session, ticket_id: str, comment: str) -> dict:
    t = _own_ticket(session, ticket_id)
    t["comments"].append(f"{session.name}: {comment}")
    return {"ticket": ticket_id.upper(), "comment_added": True}


_TICKET_ID = {"ticket_id": {"type": "string", "description": "e.g. INC0001"}}

TOOLS = [
    Tool(definition(
        "open_ticket",
        "Opens a ticket for the L2 team when the problem was not solved by the knowledge base "
        "guidance, or when the article says to open a ticket. The requester is the logged-in user.",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string", "description": "Summary of the problem and what was already tried"},
                "category": {"type": "string", "enum": ["network", "hardware", "software", "email", "access", "other"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["title", "description", "category", "priority"],
        },
    ), open_ticket),
    Tool(definition("list_my_tickets", "Lists the logged-in user's own tickets.", NO_ARGS), list_my_tickets),
    Tool(definition(
        "get_ticket_status",
        "Returns status and comments of one of the logged-in user's tickets.",
        {"type": "object", "properties": _TICKET_ID, "required": ["ticket_id"]},
    ), get_ticket_status),
    Tool(definition(
        "add_ticket_comment",
        "Adds a comment (new information from the user) to one of the logged-in user's tickets.",
        {
            "type": "object",
            "properties": {**_TICKET_ID, "comment": {"type": "string"}},
            "required": ["ticket_id", "comment"],
        },
    ), add_ticket_comment),
]
