"""Agent tools: the DEFINITION (what the LLM sees) and the IMPLEMENTATION (what our code runs).

Key point: the LLM never executes anything. It only *asks* to call a tool, with arguments.
Our code does the executing — which is why we can control what each agent is allowed to do.
"""

import json

from openai.types.chat import ChatCompletionToolParam

from src import data


def _tool(name: str, description: str, parameters: dict) -> ChatCompletionToolParam:
    """OpenAI tool format. Every provider has its own wrapper, but the 3 pieces are always the same:
    name, description and a JSON Schema for the arguments."""
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


# ---------------------------------------------------------------------------
# 1) Definitions: name + description + argument schema.
#    The description is a prompt: it's how the LLM decides WHEN to use the tool.
# ---------------------------------------------------------------------------
TOOLS: list[ChatCompletionToolParam] = [
    _tool(
        "search_knowledge_base",
        "Searches IT knowledge base articles. ALWAYS use it before guiding the user on a "
        "technical problem, so the answer follows the official procedure. Query in English.",
        {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Problem keywords, e.g. 'vpn not connecting'"}},
            "required": ["query"],
        },
    ),
    _tool(
        "get_user",
        "Returns name, department and manager of an employee by corporate email.",
        {
            "type": "object",
            "properties": {"email": {"type": "string"}},
            "required": ["email"],
        },
    ),
    _tool(
        "open_ticket",
        "Opens a ticket for the L2 team when the problem was not solved by the knowledge base "
        "guidance, or when the article says to open a ticket.",
        {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Requester's email"},
                "title": {"type": "string"},
                "description": {"type": "string", "description": "Summary of the problem and what was already tried"},
                "category": {"type": "string", "enum": ["network", "hardware", "software", "email", "access", "other"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["email", "title", "description", "category", "priority"],
        },
    ),
    _tool(
        "create_access_request",
        "Registers an access request for a folder or system. It does NOT grant access: the request "
        "stays pending until the manager approves it. A justification is required.",
        {
            "type": "object",
            "properties": {
                "email": {"type": "string"},
                "resource": {"type": "string", "description": "Folder or system, e.g. 'Finance folder'"},
                "justification": {"type": "string"},
            },
            "required": ["email", "resource", "justification"],
        },
    ),
]


# ---------------------------------------------------------------------------
# 2) Implementations: plain, deterministic Python.
# ---------------------------------------------------------------------------
def search_knowledge_base(query: str) -> list[dict]:
    # Naive keyword search, on purpose. In module 7 (RAG) we replace it with something serious.
    words = [w for w in query.lower().split() if len(w) > 2]
    scored = []
    for article in data.KB_ARTICLES:
        text = " ".join([article["title"], article["content"], *article["tags"]]).lower()
        score = sum(text.count(w) for w in words)
        if score:
            scored.append((score, article))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"id": a["id"], "title": a["title"], "content": a["content"]} for _, a in scored[:3]]


def get_user(email: str) -> dict:
    user = data.USERS.get(email.lower())
    if user is None:
        raise ValueError(f"User '{email}' not found in the directory.")
    return {"email": email.lower(), **user}


def open_ticket(email: str, title: str, description: str, category: str, priority: str) -> dict:
    ticket_id = f"INC{len(data.TICKETS) + 1:04d}"
    data.TICKETS[ticket_id] = {
        "email": email, "title": title, "description": description,
        "category": category, "priority": priority, "status": "open",
    }
    return {"ticket": ticket_id, "status": "open", "queue": "L2"}


def create_access_request(email: str, resource: str, justification: str) -> dict:
    # Decision D2: the agent only REGISTERS. Granting happens in another process, after human approval.
    user = get_user(email)
    request_id = f"REQ{len(data.ACCESS_REQUESTS) + 1:04d}"
    data.ACCESS_REQUESTS[request_id] = {
        "email": email, "resource": resource, "justification": justification,
        "approver": user["manager"], "status": "pending_approval",
    }
    return {"request": request_id, "status": "pending_approval", "approver": user["manager"]}


IMPLEMENTATIONS = {
    "search_knowledge_base": search_knowledge_base,
    "get_user": get_user,
    "open_ticket": open_ticket,
    "create_access_request": create_access_request,
}


def tools_for(names: set[str]) -> list[ChatCompletionToolParam]:
    """Subset of TOOLS — what one specialist is allowed to SEE."""
    return [t for t in TOOLS if t["function"]["name"] in names]


def run_tool(name: str, arguments: dict, allowed: set[str] | None = None) -> tuple[str, bool]:
    """Runs the tool the LLM asked for. Returns (result_as_text, is_error).

    Errors don't crash the agent: they go back to the LLM as a normal result starting with "Error:",
    and it decides what to do next (ask for the right email, try another search...).

    `allowed` is the real least-privilege lock: hiding a tool from the LLM is not enough, because it can
    still ASK for any name (hallucination, prompt injection). The code refuses what the agent doesn't own.
    """
    if allowed is not None and name not in allowed:
        return f"Error: tool '{name}' is not available to this agent.", True
    func = IMPLEMENTATIONS.get(name)
    if func is None:
        return f"Unknown tool: {name}", True
    try:
        return json.dumps(func(**arguments), ensure_ascii=False), False
    except Exception as e:  # noqa: BLE001 — any failure becomes feedback for the LLM
        return f"Error: {e}", True
