"""Service catalog: software and equipment — SERVICE REQUESTS ("I want something new"), not incidents
("something is broken", that's a ticket). The distinction comes from ITIL, and it's why this is a separate agent.

Two write tools with different contracts instead of one with an optional justification:
- order_catalog_item: pre-approved items, delivered right away — no justification, nothing to verify;
- request_catalog_approval: items that need the manager — the justification must be the user's own words.
One tool with an OPTIONAL justification would run the provenance check even when it isn't needed (and refuse a
7-Zip install because the LLM filled in a reason by itself).

Every policy is enforced here, whatever the LLM decided: blocked software, contractors, laptop age (KB012),
duplicates. The approval itself is human (decision D2) — another flow (module 4).
"""

from src import data
from src.auth import Session
from src.tools._schema import NO_ARGS, Tool, definition
from src.tools.assets import REPLACEMENT_AGE_YEARS, replacement_eligible

LAPTOP_REPLACEMENT = "HW004"


def _item(item_id: str) -> dict:
    item = data.CATALOG.get(item_id.upper())
    if item is None:
        raise ValueError(f"Catalog item {item_id} not found. Use search_catalog to find the right id.")
    if item["approval"] == "blocked":
        raise ValueError(f"{item['name']} can't be requested: {item['blocked_reason']}")
    return item


def _check_not_duplicate(session: Session, item_id: str) -> None:
    for rid, r in data.CATALOG_REQUESTS.items():
        if r["email"] == session.email and r["item"] == item_id.upper() and r["status"] != "rejected":
            raise ValueError(f"The user already requested this item: {rid} ({r['status']}).")


def _register(session: Session, item_id: str, status: str, **extra) -> dict:
    request_id = f"RITM{len(data.CATALOG_REQUESTS) + 1:04d}"
    data.CATALOG_REQUESTS[request_id] = {"email": session.email, "item": item_id.upper(), "status": status, **extra}
    return {"request": request_id, "item": data.CATALOG[item_id.upper()]["name"], "status": status, **extra}


def _item_text(arguments: dict) -> str:
    item = data.CATALOG.get(str(arguments.get("item_id", "")).upper())
    return f"{item['name']} {item['type']}" if item else ""


def search_catalog(session: Session, query: str) -> list[dict]:
    words = [w for w in query.lower().split() if len(w) > 2]
    matches = [
        {"item_id": iid, **item}
        for iid, item in data.CATALOG.items()
        if any(w in f"{item['name']} {item['type']} {item['description']}".lower() for w in words)
    ]
    if not matches:
        raise ValueError(f"No catalog item matches '{query}'. Items: {', '.join(i['name'] for i in data.CATALOG.values())}.")
    return matches


def order_catalog_item(session: Session, item_id: str) -> dict:
    item = _item(item_id)
    if item["approval"] != "pre_approved":
        raise ValueError(f"{item['name']} needs the manager's approval: use request_catalog_approval with the "
                         "user's justification.")
    _check_not_duplicate(session, item_id)
    delivery = "installed automatically within 1 hour" if item["type"] == "software" else "delivered in 2 business days"
    return _register(session, item_id, "scheduled", delivery=delivery)


def request_catalog_approval(session: Session, item_id: str, justification: str) -> dict:
    item = _item(item_id)
    if item["approval"] == "pre_approved":
        raise ValueError(f"{item['name']} is pre-approved: use order_catalog_item (no justification needed).")
    user = data.USERS[session.email]
    if user["employment"] == "contractor":
        raise ValueError("Contractors can only order pre-approved items. The contracting manager must request "
                         "licensed software or equipment for them.")
    if item_id.upper() == LAPTOP_REPLACEMENT and not any(
        replacement_eligible(d) for d in data.DEVICES.values() if d["owner"] == session.email
    ):
        raise ValueError(f"None of the user's laptops is eligible for replacement (policy: {REPLACEMENT_AGE_YEARS}+ "
                         "years old, KB012). A laptop with a hardware failure needs a Hardware ticket first.")
    _check_not_duplicate(session, item_id)
    # The approver is looked up by code (the manager), never chosen by the LLM.
    return _register(session, item_id, "pending_approval", approver=user["manager"], justification=justification)


def list_my_catalog_requests(session: Session) -> list[dict]:
    return [
        {"request": rid, "item": data.CATALOG[r["item"]]["name"], "status": r["status"]}
        for rid, r in data.CATALOG_REQUESTS.items() if r["email"] == session.email
    ]


_ITEM_ID = {"item_id": {"type": "string", "description": "Catalog id from search_catalog, e.g. SW001"}}

TOOLS = [
    Tool(definition(
        "search_catalog",
        "Searches the service catalog (software and equipment) and shows whether each item is pre-approved, "
        "needs the manager's approval, or is blocked by policy. Query in English.",
        {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "e.g. 'pdf editor', 'monitor', 'laptop'"}},
            "required": ["query"],
        },
    ), search_catalog),
    Tool(definition(
        "order_catalog_item",
        "Orders a PRE-APPROVED catalog item for the logged-in user (delivered or installed right away). "
        "Items that need approval: use request_catalog_approval.",
        {"type": "object", "properties": _ITEM_ID, "required": ["item_id"]},
    ), order_catalog_item),
    Tool(definition(
        "request_catalog_approval",
        "Requests a catalog item that needs the manager's approval (licensed software, bigger equipment). It does "
        "NOT deliver anything: the request stays pending until the manager approves. For the justification, use "
        "the reason the user gave in their own words; only if they gave no reason at all, ask for it.",
        {
            "type": "object",
            "properties": {**_ITEM_ID, "justification": {"type": "string"}},
            "required": ["item_id", "justification"],
        },
    # Found in the eval (case 42): "Solicito Adobe Acrobat Pro." passed as a justification — the only other
    # argument was "SW004", so provenance couldn't tell that "Adobe Acrobat Pro" was the REQUEST, not a reason.
    ), request_catalog_approval, from_user=("justification",), describe_request=_item_text),
    Tool(definition(
        "list_my_catalog_requests", "Lists the logged-in user's software/equipment requests and their status.",
        NO_ARGS,
    ), list_my_catalog_requests),
]
