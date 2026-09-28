"""A hub node that is ANOTHER TEAM's agent, reached over A2A (lesson 2.4). No LLM on our side: code relays.

What we know about it comes only from its Agent Card (discovery): the card's description becomes the
transfer tool our triage sees — if the IAM team adds a skill, our triage learns it without a code change.

Handoff on top of A2A: A2A is DELEGATION (a task in, an artifact out), but the user keeps talking to it
through us. Our rule, in code:
- task INPUT_REQUIRED → it asked the user something: the next user message goes to THAT task (same taskId);
- task finished        → the conversation goes back to the hub on the next turn (it can't transfer by itself:
  it doesn't take part in our team's protocol — it has no transfer_to_triage).
"""

import json

from src.auth import Session
from src.core.agent import ToolCall, Usage
from src.services.a2a_client import A2AClient
from src.services.a2a_protocol import FAILED, FINISHED, data_of, text_of


class RemoteAgent:
    def __init__(
        self, name: str, client: A2AClient, session: Session, verbose: bool = True
    ):
        self.name, self.client, self.session, self.verbose = (
            name,
            client,
            session,
            verbose,
        )
        self.task: dict | None = (
            None  # the open remote task, while it waits for the user (INPUT_REQUIRED)
        )
        self.tool_calls: list[
            ToolCall
        ] = []  # one entry per A2A exchange: what the eval can observe
        self.usage = (
            Usage()
        )  # OUR side spends no tokens here — the remote team pays for its LLM

    @property
    def handles(self) -> str:
        card = self.client.card
        skills = "; ".join(f"{s['name']}: {s['description']}" for s in card["skills"])
        return f"{card['description']} Skills — {skills}"

    def reply(self, user_text: str) -> tuple[str, bool]:
        """Relays the RAW user text (the remote agent's provenance check needs the user's own words).
        Returns (the remote agent's text, whether its task finished)."""
        open_task = self.task
        task = self.client.send(
            user_text,
            user_email=self.session.email,
            task_id=open_task and open_task["id"],
            context_id=open_task and open_task["contextId"],
        )
        state = task["status"]["state"]
        self.task = None if state in FINISHED else task
        # The eval sees what the PROTOCOL returns — state + structured data — not the opaque agent's internals.
        result = json.dumps({"state": state, "data": data_of(task)}, ensure_ascii=False)
        self.tool_calls.append(
            ToolCall(f"a2a_{self.name}", {"text": user_text}, result, state == FAILED)
        )
        if self.verbose:
            print(f"  🌐 A2A → {self.client.card['name']}: [{state}]")
        return text_of(task), state in FINISHED

    def cost(self) -> float:
        return 0.0
