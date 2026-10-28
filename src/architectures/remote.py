"""A hub node that is ANOTHER TEAM's agent, reached over A2A (lesson 2.4). No LLM on our side: code relays.

What we know about it comes only from its Agent Card (discovery): the card's description becomes the
transfer tool our triage sees — if the IAM team adds a skill, our triage learns it without a code change.

Handoff on top of A2A: A2A is DELEGATION (a task in, an artifact out), but the user keeps talking to it
through us. Our rule, in code:
- task INPUT_REQUIRED → it asked the user something: the next user message goes to THAT task (same taskId);
- task finished        → the conversation goes back to the hub IN THE SAME TURN (it can't transfer by itself:
  it doesn't take part in our team's protocol — it has no transfer_to_triage). See handoff.py.

Task ≠ context (A2A spec): a TASK is one unit of work (it ends); the CONTEXT is the conversation (it goes on).
We keep the contextId across tasks, so "and what's the status of that request?" reaches an agent that
remembers which request — a new task in the same context, not a stranger.
"""

import json
from dataclasses import dataclass

from a2a.types import TaskNotFoundError, TaskState

from src.auth import Session
from src.core.agent import ToolCall, Usage
from src.services.a2a_client import FINISHED, A2AClient, data_of, state_name, text_of


@dataclass(frozen=True)
class RemoteReply:
    text: str
    finished: bool  # the remote task ended: the conversation goes back to the hub
    task_id: str | None  # the open task (INPUT_REQUIRED) the next user message continues; None once finished
    context_id: str  # the remote conversation: outlives each task


class RemoteAgent:
    """Since module 4 it holds NO conversation state: the open task and the context are pointers into the other
    team's service, and pointers are STATE — they live in the graph's state (the checkpoint), so a restarted
    Service Desk still knows which remote task the user was answering. This object is only the live connection."""

    def __init__(self, name: str, client: A2AClient, session: Session, verbose: bool = True):
        self.name, self.client, self.session, self.verbose = name, client, session, verbose
        self.tool_calls: list[ToolCall] = []  # one entry per A2A exchange: what the eval can observe
        self.usage = Usage()  # OUR side spends no tokens here — the remote team pays for its LLM

    @property
    def handles(self) -> str:
        card = self.client.card
        skills = "; ".join(f"{s.name}: {s.description}" for s in card.skills)
        return f"{card.description} Skills — {skills}"

    def reply(self, user_text: str, task_id: str | None, context_id: str | None) -> RemoteReply:
        """Relays the RAW user text (the remote agent's provenance check needs the user's own words)."""
        try:
            task = self._send(user_text, task_id, context_id)  # continue the open task, if any; else a new one
        except TaskNotFoundError:
            # Our pointer is durable (the checkpoint), the IAM team's tasks are not (in memory): after THEIR restart
            # the saved task id points to nothing. The question it asked is lost — send the message as a new task.
            if self.verbose:
                print("  🌐 the remote task no longer exists (service restarted?): starting a new one")
            task = self._send(user_text, None, context_id)
        state, name = task.status.state, state_name(task)
        finished = state in FINISHED
        # The eval sees what the PROTOCOL returns — state + structured data — not the opaque agent's internals.
        result = json.dumps({"state": name, "data": data_of(task)}, ensure_ascii=False)
        self.tool_calls.append(
            ToolCall(f"a2a_{self.name}", {"text": user_text}, result, state == TaskState.TASK_STATE_FAILED)
        )
        if self.verbose:
            print(f"  🌐 A2A → {self.client.card.name}: [{name}]")
        return RemoteReply(text_of(task), finished, None if finished else task.id, task.context_id)

    def _send(self, text: str, task_id: str | None, context_id: str | None):
        return self.client.send(text, user_email=self.session.email, task_id=task_id, context_id=context_id,
                                on_progress=self._progress)  # streaming: "working" arrives before the answer

    def _progress(self, text: str) -> None:
        if self.verbose:
            print(f"  🌐 {self.client.card.name}: {text}")

    def cost(self) -> float:
        return 0.0
