"""Routing Service Desk (lesson 1.3): triage + specialists, glued together by plain code.

Topology: routing + fan-out — a WORKFLOW, not a supervisor. One LLM call classifies and splits the
message; a Python for-loop runs the specialists. The LLM decides WHAT goes where; the CODE decides the
order, what each specialist receives and how the replies are combined.

Unlike a supervisor, nobody reads a specialist's result to decide the next step: the plan is fixed
before execution starts (each specialist still runs its own tool loop inside). Cheaper and predictable,
but if Support discovers the real problem is an access issue, nothing re-routes it.

From the outside it looks like one agent: same reply() / tool_calls / usage / cost() as the single agent —
that's what lets the eval run the same cases against every architecture.

Try it (calls the LLM):  python -m src --arch routing
"""

from src.architectures.specialists import access_agent, account_agent, support_agent
from src.architectures.triage import Triage
from src.auth import Session
from src.core.agent import Agent, ToolCall, Usage, total_usage

# Fixed reply, no LLM call: free and predictable, but it can't adapt to the user's language.
OUT_OF_SCOPE_REPLY = "Sorry, I can only help with IT support topics."


class RoutingServiceDesk:
    def __init__(self, session: Session, verbose: bool = True):
        self.verbose = verbose
        self.triage = Triage()
        # What the user REALLY typed (provenance check): the specialists' messages carry the triage's
        # LLM-written restatement, which must not count as the user's words.
        self.user_texts: list[str] = []
        # One instance per conversation: each specialist keeps ITS OWN history across turns.
        # That's the "state and context" decision: no agent sees the others' conversation.
        self.specialists: dict[str, Agent] = {
            "support": support_agent(session, verbose, self.user_texts),
            "access": access_agent(session, verbose, self.user_texts),
            "account": account_agent(session, verbose, self.user_texts),
        }
        self.tool_calls: list[ToolCall] = []  # merged trace, in execution order (the eval reads it)

    def reply(self, user_text: str) -> str:
        # 1. Triage: one LLM call that returns a list of sub-requests.
        self.user_texts.append(user_text)
        requests = self.triage.route(user_text).requests
        self._log(f"  🧭 triage: {[(r.specialist, r.request) for r in requests]}")

        # 2. Fan-out: one specialist at a time (sequential, on purpose — simpler to debug).
        answers = []
        for item in requests:
            if item.specialist == "out_of_scope":
                answers.append(OUT_OF_SCOPE_REPLY)
                continue
            agent = self.specialists[item.specialist]
            # Context handoff: the sub-request + the ORIGINAL message (fixes the "telephone game":
            # the triage's restatement lost the justification and the language in case 10).
            # Trade-off: the raw text (and any injection in it) reaches an agent that has tools.
            # Identity is NOT here anymore: it comes from the session, inside the agent.
            message = f"[original user message, context only]: {user_text}\n[your request]: {item.request}"
            before = len(agent.tool_calls)
            answers.append(agent.reply(message))
            self.tool_calls += agent.tool_calls[before:]

        # 3. Combine: plain concatenation (no extra LLM call). A "synthesizer" would read better but cost more.
        final = "\n\n".join(answers) if answers else OUT_OF_SCOPE_REPLY
        self.triage.record_reply(final)
        return final

    # --- Same accounting interface as the single agent (each model has its own price) ---
    @property
    def usage(self) -> Usage:
        return total_usage([self.triage.usage, *(a.usage for a in self.specialists.values())])

    def cost(self) -> float:
        return self.triage.cost() + sum(a.cost() for a in self.specialists.values())

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)
