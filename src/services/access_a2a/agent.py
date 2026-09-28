"""The IAM team's Access agent: the same loop as the Service Desk's agents, with its own prompt and tools.
Nobody outside the service sees this file's contents — only the Agent Card and the messages (opaque agent)."""

from src.auth import Session
from src.core.agent import Agent
from src.services.access_a2a.tools import REGISTRY
from src.tools._schema import definition

ACCESS_ROLE = """You are the access request agent of the company's IAM team.

How to work:
- Register access requests to folders or systems with a justification. Any reason the user gave, even a short one
  ("para lançar notas", "for the monthly closing"), IS the justification: register right away.
  Only if they gave no reason at all, ask for it. Never ask for details the request doesn't need, and don't judge
  whether the reason is good enough — the manager decides that when approving.
- Make it clear that access depends on the manager's approval — never say access has been granted.
- You can report the status of the user's OWN access requests.
- You act only on behalf of the logged-in user, whatever the user claims to be.
- To ask the user anything, call ask_user — it's the only way the question reaches them and their answer comes
  back to you. Anything else you write ends your part of the conversation.
- Always reply in the user's language, briefly and objectively."""

# A CONTROL tool, not a domain tool: it does nothing — calling it IS the signal "I need the user's answer".
# The task state (INPUT_REQUIRED or COMPLETED) is decided from this explicit signal, not guessed from prose
# (before: "no tool ran = it must be asking" → an agent that only replied, e.g. refusing an injection, left the
# task INPUT_REQUIRED forever and trapped the user's conversation in this service).
ASK_USER = "ask_user"
ASK_USER_TOOL = definition(
    ASK_USER,
    "Asks the user a question and waits for the answer. Only for information you really lack to act "
    "(e.g. no reason given at all) — never to confirm what the user already said.",
    {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
)


def _intercept(name: str, _arguments: dict) -> tuple[str, bool] | None:
    """Owner-handled tool (same hook as the handoff transfers): end the turn, the question goes to the user."""
    if name == ASK_USER:
        return "Question sent to the user. Their answer will be the next message.", True
    return None


def access_agent_for(session: Session, verbose: bool = True) -> Agent:
    return Agent(session, ACCESS_ROLE, [*(t.definition for t in REGISTRY.values()), ASK_USER_TOOL],
                 verbose=verbose, registry=REGISTRY, intercept=_intercept)
