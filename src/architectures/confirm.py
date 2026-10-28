"""Human-in-the-loop with the USER (lesson 4.4): calls the code won't run until the user confirms them.

Two calls that a flag or a word count can't settle, because only the user knows:
- an argument that must be the user's own words (`from_user`) but is only PROBABLY theirs — between check()'s 50%
  and 100% of the words (eval case 42: "Adobe Acrobat Pro" + invented words passed at exactly 50%);
- `open_ticket` with force_new=true: the LLM set that flag by itself, so it proved nothing (module 3's comment).

How (option "A+" of lesson 4.1): the agent's loop does NOT pause. The desk intercepts the call, the agent's node
ends, and a separate CONFIRM node calls interrupt(). On resume LangGraph re-runs the interrupted node from the
start — here that node has nothing before the interrupt, so no LLM call repeats (paid twice, maybe decided
differently). The side effect (running the tool) comes AFTER the interrupt, so it runs once.

The prompt is written by the CODE from the real arguments: the LLM could describe the request one way and call
the tool another. What the user confirms is exactly what will run.
"""

from src.tools import provenance
from src.tools._schema import Tool

# Every word of the answer must be one of these, and at least one a real "yes". Anything else (even "sim, mas
# o motivo é outro") is NOT a confirmation: it goes back to the agent as the user's message (fails safe, D9).
_YES = {"sim", "s", "yes", "y", "ok", "confirmo", "confirma", "confirmado", "pode", "isso", "certo", "claro"}
_FILLER = {"pode", "registrar", "registra", "abrir", "abre", "por", "favor", "pf", "pfv", "obrigado", "obrigada"}


def prompt_for(tool: Tool, arguments: dict, user_texts: list[str]) -> str | None:
    """The question for the user, if this call needs their confirmation; None to run it as usual."""
    if tool.name == "open_ticket" and arguments.get("force_new"):
        return (f"You already have an open ticket about this. Open a NEW, separate ticket anyway?\n"
                f"  title: {arguments.get('title', '')}\n"
                "Reply \"yes\" to open it, or tell me what you'd like instead.")
    for arg in tool.from_user:
        value, request = str(arguments.get(arg, "")), provenance.request_text(arguments, arg)
        # Clearly NOT the user's words → None: run_tool refuses it and the LLM asks the user (as before).
        # Only the user's words → None: runs. In between → the user decides.
        if provenance.check(arg, value, user_texts, request) is None and not provenance.verbatim(value, user_texts, request):
            shown = ", ".join(f"{k}: {v}" for k, v in arguments.items() if k != arg)
            return (f"Please confirm before I send it ({tool.name}, {shown}):\n"
                    f"  {arg}: \"{value}\"\n"
                    f"Reply \"yes\" if that's your reason, or write it in your own words.")
    return None


def is_yes(answer: str) -> bool:
    words = {w.strip(".,!;:") for w in answer.lower().split()} - {""}
    return bool(words & _YES) and words <= _YES | _FILLER


def endorsed(tool: Tool, arguments: dict) -> list[str]:
    """After a "yes", the confirmed values ARE the user's words: they join the provenance source of truth."""
    return [str(arguments.get(arg, "")) for arg in tool.from_user]


# What an agent hears when the code holds one of its calls for the user's confirmation...
CONFIRM_ASKED = (
    "Not run yet: the code is asking the user to confirm this exact call. Write nothing now — their answer comes "
    "back to you."
)
# ...and what it hears after the user answered. The CODE ran the tool (or didn't): the agent only reports.
CONFIRMED = "The user confirmed and the code ran {tool}. Result: {result}. Tell the user the outcome; don't call it again."
NOT_CONFIRMED = (
    "The user did NOT confirm {tool}: their answer is the last user message. Act on it — if they gave their reason "
    "in their own words, call {tool} again with those words."
)
