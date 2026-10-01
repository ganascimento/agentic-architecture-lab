"""Knowledge base + system status: read-only, no personal data.

The KB has INTERNAL articles (runbooks, admin procedures): only the IT department sees them. The filter is in
CODE, in every read path (search AND read by id) — a prompt saying "don't show internal articles" would be
one injection away from leaking them. A public article even points to an internal one (KB003 → KB017):
knowing the id is not permission, the same lesson as IDOR on tickets.
"""

from src import data
from src.auth import Session
from src.tools._schema import NO_ARGS, Tool, definition


def _visible_articles(session: Session) -> list[dict]:
    it_staff = data.USERS[session.email]["department"] == "IT"
    return [a for a in data.KB_ARTICLES if a["visibility"] == "public" or it_staff]


def search_knowledge_base(session: Session, query: str) -> list[dict]:
    # Naive keyword search, on purpose. In module 7 (RAG) we replace it with something serious.
    words = [w for w in query.lower().split() if len(w) > 2]
    scored = []
    for article in _visible_articles(session):
        text = " ".join([article["title"], article["content"], *article["tags"]]).lower()
        score = sum(text.count(w) for w in words)
        if score:
            scored.append((score, article))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"id": a["id"], "title": a["title"], "content": a["content"]} for _, a in scored[:3]]


def get_kb_article(session: Session, article_id: str) -> dict:
    for article in _visible_articles(session):
        if article["id"] == article_id.upper():
            return {k: article[k] for k in ("id", "title", "category", "updated", "content")}
    # Same error for "doesn't exist" and "you can't see it": the error must not confirm an internal article exists.
    raise ValueError(f"Article {article_id} not found.")


def check_system_status(session: Session, system: str) -> dict:
    status = data.SYSTEM_STATUS.get(system.lower())
    if status is None:
        raise ValueError(f"Unknown system '{system}'. Known: {', '.join(data.SYSTEM_STATUS)}.")
    return {"system": system.lower(), **status}


def list_active_incidents(session: Session) -> dict:
    return {
        "incidents": [{"system": name, **s} for name, s in data.SYSTEM_STATUS.items() if s["status"] != "operational"],
        "scheduled_maintenance": [
            {"system": name, **s["maintenance"]} for name, s in data.SYSTEM_STATUS.items() if "maintenance" in s
        ],
    }


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
        "get_kb_article",
        "Reads one knowledge base article by its id (e.g. when an article or the user mentions 'KB012'). "
        "To find articles about a problem, use search_knowledge_base instead.",
        {
            "type": "object",
            "properties": {"article_id": {"type": "string", "description": "e.g. KB012"}},
            "required": ["article_id"],
        },
    ), get_kb_article),
    Tool(definition(
        "check_system_status",
        "Checks whether ONE corporate system has an ongoing incident (outage or slowness) or scheduled maintenance.",
        {
            "type": "object",
            "properties": {"system": {"type": "string", "enum": list(data.SYSTEM_STATUS)}},
            "required": ["system"],
        },
    ), check_system_status),
    Tool(definition(
        "list_active_incidents",
        "Lists every ongoing incident and scheduled maintenance, across all systems. Use it when the user asks "
        "in general ('is anything down?'); for one specific system, use check_system_status.",
        NO_ARGS,
    ), list_active_incidents),
]
