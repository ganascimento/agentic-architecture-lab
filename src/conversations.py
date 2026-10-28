"""Where the Service Desk's conversations are saved (lesson 4.3): a SQLite checkpointer + who owns which thread.

A thread_id is a POINTER, not a permission (lesson 4.1, section 9). Whoever has the id of someone else's thread
can read it — and, from lesson 4.4 on, answer a confirmation in that person's name. So the user never TYPES a
thread id: the code builds it from the logged-in Session ("<email>/<number>"), the same way tools never take
the user's identity from the LLM (D4). Ana's "/open 2" can only ever mean "ana@company.com/2".

SQLite is the dev choice: one file, survives a restart, no server. In production: Postgres (concurrent writers,
backups) — the same checkpointer interface, another class. The file is git-ignored (it holds conversations).
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from src.auth import Session

STATE_DIR = Path(__file__).resolve().parents[1] / ".state"
DB_PATH = STATE_DIR / "service_desk.sqlite"


def open_store(path: Path = DB_PATH) -> SqliteSaver:
    path.parent.mkdir(exist_ok=True)
    # check_same_thread=False: LangGraph may write a checkpoint from a worker thread; SqliteSaver serializes access.
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False))


def thread_id(session: Session, number: int) -> str:
    return f"{session.email}/{number}"


def threads_of(store: SqliteSaver, session: Session) -> list[int]:
    """The numbers of the logged-in user's conversations, oldest first. Only their own: filtered by the prefix the
    CODE wrote. (Scans every checkpoint: fine for a dev file; a real app keeps a conversations table.)"""
    prefix = f"{session.email}/"
    numbers = {
        int(tid.removeprefix(prefix))
        for c in store.list(None)
        if (tid := c.config.get("configurable", {}).get("thread_id", "")).startswith(prefix) and tid.removeprefix(prefix).isdigit()
    }
    return sorted(numbers)


def title(store: SqliteSaver, session: Session, number: int) -> str:
    """The conversation's first user message — enough to tell them apart in /threads."""
    saved = store.get_tuple({"configurable": {"thread_id": thread_id(session, number)}})
    messages = saved.checkpoint["channel_values"].get("messages", []) if saved else []
    return next((m["content"][:60] for m in messages if m["role"] == "user"), "(empty)")
