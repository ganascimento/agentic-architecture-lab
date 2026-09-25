"""Multi-agent Service Desk: triage + specialists, glued together by plain code.

Topology: routing + fan-out — a WORKFLOW, not a supervisor. One LLM call classifies and splits the
message; a Python for-loop runs the specialists. The LLM decides WHAT goes where; the CODE decides the
order, what each specialist receives and how the replies are combined.

Unlike a supervisor, nobody reads a specialist's result to decide the next step: the plan is fixed
before execution starts (each specialist still runs its own tool loop inside). Cheaper and predictable,
but if Support discovers the real problem is an access issue, nothing re-routes it.

From the outside it looks like one agent: same reply() / tool_calls / usage / cost() as
ServiceDeskAgent — that's what lets the eval run the same cases against both.

Try it (calls the LLM):  python -m src.multi_agent
"""

from src.agent import ServiceDeskAgent, ToolCall, Usage
from src.specialists import access_agent, support_agent
from src.triage import Triage

# Fixed reply, no LLM call: free and predictable, but it can't adapt to the user's language.
OUT_OF_SCOPE_REPLY = "Sorry, I can only help with IT support topics."


class MultiAgentServiceDesk:
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.triage = Triage()
        # One instance per conversation: each specialist keeps ITS OWN history across turns.
        # That's the "state and context" decision: no agent sees the others' conversation.
        self.specialists: dict[str, ServiceDeskAgent] = {
            "support": support_agent(verbose),
            "access": access_agent(verbose),
        }
        self.user_email: str | None = None
        self.tool_calls: list[ToolCall] = []  # merged trace, in execution order (the eval reads it)

    def reply(self, user_text: str) -> str:
        # 1. Triage: one LLM call that returns a list of sub-requests.
        result = self.triage.route(user_text)
        self.user_email = result.user_email or self.user_email  # remember it across turns
        requests = result.requests or []
        self._log(f"  🧭 triage: {[(r.specialist, r.request) for r in requests]} | email={self.user_email}")

        # 2. Fan-out: one specialist at a time (sequential, on purpose — simpler to debug).
        answers = []
        for item in requests:
            if item.specialist == "out_of_scope":
                answers.append(OUT_OF_SCOPE_REPLY)
                continue
            agent = self.specialists[item.specialist]
            # Context handoff: sub-request + identity + the ORIGINAL message (fixes the "telephone game":
            # the triage's restatement lost the justification and the language in case 10).
            # Trade-off: the raw text (and any injection in it) now reaches an agent that has tools.
            message = (
                f"[user email: {self.user_email or 'unknown'}]\n"
                f"[original user message, context only]: {user_text}\n"
                f"[your request]: {item.request}"
            )
            before = len(agent.tool_calls)
            answers.append(agent.reply(message))
            self.tool_calls += agent.tool_calls[before:]

        # 3. Combine: plain concatenation (no extra LLM call). A "synthesizer" would read better but cost more.
        final = "\n\n".join(answers) if answers else OUT_OF_SCOPE_REPLY
        self.triage.record_reply(final)
        return final

    # --- Same accounting interface as ServiceDeskAgent (each model has its own price) ---
    @property
    def usage(self) -> Usage:
        parts = [self.triage.usage, *(a.usage for a in self.specialists.values())]
        return Usage(
            calls=sum(u.calls for u in parts),
            input_tokens=sum(u.input_tokens for u in parts),
            output_tokens=sum(u.output_tokens for u in parts),
        )

    def cost(self) -> float:
        return self.triage.usage.cost(self.triage.model.name) + sum(a.cost() for a in self.specialists.values())

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)


if __name__ == "__main__":
    desk = MultiAgentServiceDesk()
    for turn in ["sou joao@company.com, a vpn caiu desde ontem e preciso de acesso ao SAP para lançar notas"]:
        print(f"\nyou> {turn}")
        print(f"\nagent> {desk.reply(turn)}")
    print(f"\n[{desk.usage.calls} calls | US$ {desk.cost():.6f}]")
