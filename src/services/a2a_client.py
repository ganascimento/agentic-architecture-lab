"""A2A client — on the official SDK (lesson 2.3). Lesson 2.2 hand-wrote it with urllib (see git history).

The two things a client does: DISCOVER (read the Agent Card) and SEND. It knows nothing about the other
agent's prompt, model or tools — only the card and the messages.

SEND with streaming: the server pushes events (WORKING → INPUT_REQUIRED / artifact → COMPLETED) as they happen,
so we can show progress instead of a frozen terminal. Streaming delivers loose EVENTS, not the assembled Task;
at the end we ask for the whole Task once (GetTask) — one source of truth for state, question and artifacts.

Our hub is synchronous and the SDK is asyncio: each call runs in its own event loop (asyncio.run).
Trade-off: simplest bridge, but a new HTTP connection per message (no keep-alive). A long-lived loop in a
background thread would reuse connections — worth it only at volume.

Demo (with the server running in another terminal):  python -m src.services.a2a_client
"""

import asyncio
from collections.abc import Callable

import httpx
from a2a.client import A2ACardResolver, ClientCallContext, ClientConfig, ClientFactory
from a2a.helpers import get_artifact_text, get_data_parts, get_message_text, new_text_message
from a2a.types import AgentCard, GetTaskRequest, Role, SendMessageRequest, Task, TaskState

from src.services.a2a_protocol import USER_HEADER

DISCOVERY_TIMEOUT, SEND_TIMEOUT = 5, 600  # finding the card should be fast; the remote LLM may not be (10 min)
# Mirrors the SDK's TERMINAL_TASK_STATES — which lives in its SERVER internals (a client shouldn't import those).
FINISHED = {TaskState.TASK_STATE_COMPLETED, TaskState.TASK_STATE_FAILED, TaskState.TASK_STATE_CANCELED,
            TaskState.TASK_STATE_REJECTED}

OnProgress = Callable[[str], None]  # receives the agent's status text ("Checking your request...")


class A2AClient:
    def __init__(self, base_url: str):
        self.card: AgentCard = asyncio.run(self._discover(base_url))

    @staticmethod
    async def _discover(base_url: str) -> AgentCard:
        async with httpx.AsyncClient(timeout=DISCOVERY_TIMEOUT) as http:
            return await A2ACardResolver(http, base_url).get_agent_card()  # where to call comes from the card

    def send(self, text: str, user_email: str, task_id: str | None = None, context_id: str | None = None,
             on_progress: OnProgress | None = None) -> Task:
        """Sends a message; returns the Task once it's COMPLETED or INPUT_REQUIRED (streaming in between)."""
        # task_id: continuing an interrupted task (it asked us something); context_id: the conversation, across tasks
        message = new_text_message(text, context_id=context_id, task_id=task_id, role=Role.ROLE_USER)
        # ⚠️ Naive identity (see server.py NaiveIdentity): replaced by a signed token in lesson 2.5.
        call = ClientCallContext(service_parameters={USER_HEADER: user_email})

        async def run() -> Task:
            async with httpx.AsyncClient(timeout=SEND_TIMEOUT) as http:
                client = ClientFactory(ClientConfig(httpx_client=http)).create(self.card)
                seen_task_id = task_id
                async for event in client.send_message(SendMessageRequest(message=message), context=call):
                    kind = event.WhichOneof("payload")
                    if kind == "task":
                        seen_task_id = event.task.id
                    elif kind == "status_update":
                        seen_task_id = event.status_update.task_id
                        status = event.status_update.status
                        if status.state == TaskState.TASK_STATE_WORKING and on_progress:
                            on_progress(get_message_text(status.message, " "))
                # history_length=0: we read status and artifacts, not the (growing) message history
                return await client.get_task(GetTaskRequest(id=seen_task_id, history_length=0), context=call)

        return asyncio.run(run())


def state_name(task: Task) -> str:
    return TaskState.Name(task.status.state)  # "TASK_STATE_COMPLETED" — the spec's name, for logs and the eval


def text_of(task: Task) -> str:
    """What the remote agent said: the question (INPUT_REQUIRED) or the result artifact (COMPLETED)."""
    if task.status.state == TaskState.TASK_STATE_INPUT_REQUIRED:
        return get_message_text(task.status.message, " ")
    return " ".join(get_artifact_text(a, " ") for a in task.artifacts)


def data_of(task: Task) -> dict:
    """The structured part of the artifacts — for machines (the caller doesn't parse prose to know what happened)."""
    return {k: v for a in task.artifacts for d in get_data_parts(a.parts) for k, v in d.items()}


if __name__ == "__main__":
    client = A2AClient("http://localhost:8001")
    print(f"Discovered: {client.card.name} — skills: {[s.id for s in client.card.skills]}")
    progress = lambda text: print(f"  … {text}")  # noqa: E731
    task = client.send("preciso de acesso ao SAP", user_email="joao@company.com", on_progress=progress)
    print(f"[{state_name(task)}] {text_of(task)}")
    if task.status.state == TaskState.TASK_STATE_INPUT_REQUIRED:  # the remote agent asked; WE ask the user
        task = client.send("é para lançar as notas fiscais do mês", user_email="joao@company.com",
                           task_id=task.id, context_id=task.context_id, on_progress=progress)
        print(f"[{state_name(task)}] {text_of(task)}")
