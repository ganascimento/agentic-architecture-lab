"""The simplest possible authentication: local accounts + a Session object.

The architectural point (fixes Finding 1.2): identity comes from the LOGIN, never from the chat.
The session is injected by the code into every tool; the LLM never fills in "who the user is".
The LLM can still be told who is logged in (to greet, to reply), but that's information, not authority.
"""

from dataclasses import dataclass

from src import data


@dataclass(frozen=True)
class Session:
    email: str
    name: str


def login(username: str, password: str) -> Session | None:
    for account in data.ACCOUNTS:
        # ⚠️ Plaintext comparison — study only. Real systems: slow hash + constant-time compare, or an IdP.
        if account["username"] == username and account["password"] == password:
            return session_for(account["email"])
    return None


def session_for(email: str) -> Session:
    """Session without a password — for tests and evals (the "user already logged in")."""
    return Session(email=email, name=data.USERS[email]["name"])
