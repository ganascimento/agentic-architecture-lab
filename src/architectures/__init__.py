"""The architectures under study. Different classes, same shape — so the chat and the eval treat them alike."""

from collections.abc import Callable
from typing import Protocol

from src.architectures.handoff import HandoffServiceDesk
from src.architectures.routing import RoutingServiceDesk
from src.architectures.single import single_agent
from src.auth import Session
from src.core.agent import ToolCall, Usage


class ServiceDesk(Protocol):
    """What the chat and the eval need from an architecture (structural typing: no common base class)."""

    tool_calls: list[ToolCall]

    @property
    def usage(self) -> Usage: ...
    def reply(self, user_text: str) -> str: ...
    def cost(self) -> float: ...


ARCHITECTURES: dict[str, Callable[[Session, bool], ServiceDesk]] = {
    "single": single_agent,          # lesson 1.2: one agent, every tool
    "routing": RoutingServiceDesk,   # lesson 1.3: triage + specialists (workflow)
    "handoff": HandoffServiceDesk,   # lesson 1.4: agents transfer the conversation (peer-to-peer)
}
