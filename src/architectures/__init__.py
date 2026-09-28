"""The Service Desk. Since module 2 there's ONE architecture: the handoff hub, with Access as a remote A2A agent.
(Module 1's single / routing / mesh live in the `module-1` branch.)"""

from src.architectures.handoff import HandoffServiceDesk
from src.auth import Session
from src.config import ACCESS_AGENT_URL
from src.services.a2a_client import A2AClient


def service_desk(session: Session, verbose: bool = True, access: A2AClient | None = None) -> HandoffServiceDesk:
    # Discovery happens here: reading the Access agent's card. If the service is down, this fails — on purpose,
    # it's a real dependency now (another team's service), not a function in our process.
    # Trade-off: re-discovering on every new conversation sees card changes at once; reusing a client (the eval)
    # is cheaper but a stale card means our triage learns a new skill only on the next discovery.
    return HandoffServiceDesk(session, access or A2AClient(ACCESS_AGENT_URL), verbose)
