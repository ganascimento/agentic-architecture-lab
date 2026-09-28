"""Shared test fixtures — no LLM anywhere: a fake Access agent served over real A2A (HTTP on a free port)."""

import pytest

from src.core.agent import ToolCall, Usage
from src.services.a2a_client import A2AClient
from src.services.access_a2a.server import AccessA2AService, start


class FakeAccessAgent:
    """Asks for the justification first, then 'registers' the request — like the real one, without an LLM."""

    def __init__(self, session):
        self.session, self.tool_calls, self.usage = session, [], Usage()  # same shape as a real Agent

    def reply(self, text: str) -> str:
        if "justific" in text or "fechamento" in text:
            self.tool_calls.append(ToolCall("create_access_request", {}, '{"request": "REQ0002"}', False))
            return f"Registered REQ0002 for {self.session.email}"
        return "What is the justification?"

    def cost(self) -> float:
        return 0.0


@pytest.fixture
def client():
    """A client that already discovered a fake Access agent served over real A2A."""
    server, url = start(AccessA2AService(make_agent=FakeAccessAgent))
    yield A2AClient(url)
    server.shutdown()
