"""Knowledge base + system status: read-only, no personal data."""

from src import data
from src.auth import Session
from src.tools._schema import Tool, definition


def search_knowledge_base(session: Session, query: str) -> list[dict]:
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


def check_system_status(session: Session, system: str) -> dict:
    status = data.SYSTEM_STATUS.get(system.lower())
    if status is None:
        raise ValueError(f"Unknown system '{system}'. Known: {', '.join(data.SYSTEM_STATUS)}.")
    return {"system": system.lower(), **status}


TOOLS = [
    Tool(definition(
        "search_knowledge_base",
        "Searches IT knowledge base articles. ALWAYS use it before guiding the user on a "
        "technical problem, so the answer follows the official procedure. Query in English.",
        {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Problem keywords, e.g. 'vpn not connecting'"}},
            "required": ["query"],
        },
    ), search_knowledge_base),
    Tool(definition(
        "check_system_status",
        "Checks whether a corporate system has an ongoing incident (outage or slowness).",
        {
            "type": "object",
            "properties": {"system": {"type": "string", "enum": list(data.SYSTEM_STATUS)}},
            "required": ["system"],
        },
    ), check_system_status),
]
