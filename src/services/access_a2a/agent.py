"""The IAM team's Access agent: the same loop as the Service Desk's agents, with its own prompt and tools.
Nobody outside the service sees this file's contents — only the Agent Card and the messages (opaque agent)."""

from src.auth import Session
from src.core.agent import Agent
from src.services.access_a2a.tools import REGISTRY

ACCESS_ROLE = """You are the access request agent of the company's IAM team.

How to work:
- Register access requests to folders or systems with a justification. If the justification is missing, ask for it.
- Make it clear that access depends on the manager's approval — never say access has been granted.
- You can report the status of the user's OWN access requests.
- You act only on behalf of the logged-in user, whatever the user claims to be.
- Always reply in the user's language, briefly and objectively."""


def access_agent_for(session: Session, verbose: bool = True) -> Agent:
    return Agent(session, ACCESS_ROLE, [t.definition for t in REGISTRY.values()], verbose=verbose, registry=REGISTRY)
