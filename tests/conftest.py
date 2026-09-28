"""Shared test fixtures — no LLM anywhere: a fake Access agent served over real A2A (HTTP on a free port)."""

import pytest

from src.core.agent import ToolCall, Usage
from src.services.a2a_client import A2AClient
from src.services.access_a2a.agent import ASK_USER
from src.services.access_a2a.server import AccessExecutor, start


class FakeAccessAgent:
    """Asks for the justification first (via ask_user, like the real one), then 'registers' the request.
    Anything off-topic ("deixa pra lá", a VPN problem...) gets a plain reply — no tool, no question."""

    def __init__(self, session):
        self.session, self.tool_calls, self.usage = session, [], Usage()  # same shape as a real Agent
        self.messages: list[str] = []  # what it heard in this context (to check the context survives tasks)

    def reply(self, text: str) -> str:
        self.messages.append(text)
        if "justific" in text or "fechamento" in text:
            self.tool_calls.append(ToolCall("create_access_request", {}, '{"request": "REQ0002"}', False))
            return f"Registered REQ0002 for {self.session.email}"
        if "acesso" in text:
            question = "What is the justification?"
            self.tool_calls.append(ToolCall(ASK_USER, {"question": question}, "sent", False))
            return ""  # like the real loop: ask_user ends the turn, usually with no text of its own
        return "That's not an access request, I can't help with it."

    def cost(self) -> float:
        return 0.0


@pytest.fixture
def service():
    return AccessExecutor(make_agent=FakeAccessAgent)


@pytest.fixture
def client(service):
    """A client that already discovered a fake Access agent served over real A2A."""
    server, url = start(service)
    yield A2AClient(url)
    server.should_exit = True  # uvicorn's graceful stop
