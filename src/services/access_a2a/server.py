"""The Access agent as an independent A2A service — on the official SDK (lesson 2.3; `a2a-sdk`, spec v1.0).

Imagine this runs on the IAM team's infrastructure. From the outside it's OPAQUE: callers see the Agent Card
and the messages; the prompt, the model and the tools stay inside.

What the SDK took off our hands (lesson 2.2 did it by hand, see git history): JSON-RPC parsing and errors,
the task store, building Task/status/artifact objects, validating the spec's types — and it adds, for free,
streaming (SSE), GetTask, CancelTask and push notifications.
What is STILL OURS, because no SDK knows our business:
- the task STATE decision (ask_user → INPUT_REQUIRED, anything else → COMPLETED), in `AccessExecutor.execute`;
- the agent's memory per conversation (the SDK stores tasks, not our LLM's history);
- who the user is (the SDK asks us through a ServerCallContextBuilder — see NaiveIdentity).

Run:  python -m src.services.access_a2a        (port 8001)
"""

import asyncio
import json
import socket
import threading
import time
from collections.abc import Callable

import uvicorn
from a2a.auth.user import User
from a2a.helpers import new_data_part, new_task_from_user_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    DefaultServerCallContextBuilder,
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    InvalidParamsError,
)
from a2a.utils import AGENT_CARD_WELL_KNOWN_PATH
from a2a.utils.constants import PROTOCOL_VERSION_CURRENT, TransportProtocol
from starlette.applications import Starlette
from starlette.requests import Request

from src.auth import Session, session_for
from src.core.agent import Agent, Usage, total_usage
from src.services.a2a_protocol import USER_HEADER
from src.services.access_a2a.agent import ASK_USER, access_agent_for

PORT = 8001
RPC_PATH = "/a2a"


def agent_card(port: int) -> AgentCard:
    """The contract. Now a TYPED object: a misspelled field fails here, not when another team calls us."""
    return AgentCard(
        name="Access Request Agent",
        description="Registers access requests to folders and systems (pending manager approval) and reports "
        "their status. Never grants access.",
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(
                url=f"http://localhost:{port}{RPC_PATH}",
                protocol_binding=TransportProtocol.JSONRPC,
                protocol_version=PROTOCOL_VERSION_CURRENT,
            )
        ],
        # streaming=True: the caller can watch progress (SSE) instead of staring at a silent terminal.
        capabilities=AgentCapabilities(streaming=True, push_notifications=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain", "application/json"],
        skills=[
            AgentSkill(
                id="access-request",
                name="Register an access request",
                description="Registers a request for access to a folder or system, with the user's "
                "justification.",
                tags=["access", "permission", "iam"],
                examples=[
                    "I need access to the Finance folder for the monthly closing"
                ],
            ),
            AgentSkill(
                id="access-status",
                name="Access request status",
                description="Lists the user's access requests and their approval status.",
                tags=["access", "status"],
                examples=["Was my SAP access request approved?"],
            ),
        ],
    )


# --- Who is calling ---------------------------------------------------------------------------------------
class EmailUser(User):
    def __init__(self, email: str):
        self.email = email

    @property
    def is_authenticated(self) -> bool:
        return bool(self.email)

    @property
    def user_name(
        self,
    ) -> (
        str
    ):  # the SDK's task store is scoped by this: one user can't see another's tasks
        return self.email


class NaiveIdentity(DefaultServerCallContextBuilder):
    """⚠️ INSECURE ON PURPOSE (lesson 2.2's flaw, moved to the right place): the caller SAYS who the user is in a
    header, and we believe it. Anyone who can reach this port can act as anyone.
    The PLACE is right, though: the SDK asks "who is this?" here, per request, before any business code runs.
    Lesson 2.5 keeps this seam and swaps the header for a signed token that we VERIFY."""

    def build_user(self, request: Request) -> User:
        return EmailUser(request.headers.get(USER_HEADER, ""))


# --- The agent behind the protocol ------------------------------------------------------------------------
class AccessExecutor(AgentExecutor):
    """The SDK calls execute() once per message; we publish what happened as events (TaskUpdater)."""

    def __init__(self, make_agent: Callable[[Session], Agent] = access_agent_for):
        self.make_agent = make_agent
        # (user, contextId) → the agent holding that conversation. The user is PART OF THE KEY: someone else's
        # contextId just opens a fresh conversation of your own — the IDOR is impossible by construction.
        self.agents: dict[tuple[str, str], Agent] = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        email = context.call_context.user.user_name
        try:
            session = session_for(email)
        except KeyError:
            raise InvalidParamsError(message=f"Unknown user: {email!r}") from None
        if (
            context.current_task is None
        ):  # a new task: it must exist before any status update
            await event_queue.enqueue_event(new_task_from_user_message(context.message))
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        # WORKING: with streaming, the caller sees this right away — while our LLM is still thinking.
        await updater.start_work(
            updater.new_agent_message([new_text_part("Checking your request...")])
        )

        key = (email, context.context_id)
        if key not in self.agents:
            self.agents[key] = self.make_agent(session)
        agent = self.agents[key]
        before = len(agent.tool_calls)
        # Our Agent is synchronous (sync OpenAI client); the SDK is asyncio. to_thread = the simplest bridge
        # (the alternative, AsyncOpenAI, would rewrite the loop for no gain here).
        reply = await asyncio.to_thread(agent.reply, context.get_user_input())
        calls = agent.tool_calls[before:]
        question = next(
            (c.arguments.get("question", "") for c in calls if c.name == ASK_USER), None
        )

        # The STATE is the code's decision, from an EXPLICIT signal — the SDK only publishes it.
        # ask_user → INPUT_REQUIRED; anything else → COMPLETED (fails safe: never traps the caller's conversation).
        if question is not None:
            await updater.requires_input(
                updater.new_agent_message([new_text_part(reply or question)])
            )
            return
        # Text for the human, DATA for the machine (the caller doesn't parse prose to know what happened).
        parts = [new_text_part(reply)]
        if result := _business_result([c for c in calls if not c.is_error]):
            parts.append(new_data_part(result))
        await updater.add_artifact(parts, name="result")
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Our tasks last seconds and end in INPUT_REQUIRED or COMPLETED: nothing long-running to stop.
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()

    # --- The IAM team's own bill (the eval adds it to ours to compare with module 1) ---
    @property
    def usage(self) -> Usage:
        return total_usage([a.usage for a in self.agents.values()])

    def cost(self) -> float:
        return sum(a.cost() for a in self.agents.values())


def _business_result(calls: list) -> dict:
    result: dict = {}
    for call in calls:
        if call.name == "create_access_request":
            result["accessRequest"] = json.loads(call.result)
        elif call.name == "list_my_access_requests":
            result["accessRequests"] = json.loads(call.result)
    return result


# --- Serving: the SDK builds the routes, Starlette + uvicorn serve them -----------------------------------
def make_app(service: AccessExecutor, port: int) -> Starlette:
    card = agent_card(port)
    handler = DefaultRequestHandler(
        agent_executor=service, task_store=InMemoryTaskStore(), agent_card=card
    )
    routes = [
        *create_agent_card_routes(agent_card=card),  # GET /.well-known/agent-card.json
        *create_jsonrpc_routes(handler, RPC_PATH, context_builder=NaiveIdentity()),
    ]
    return Starlette(routes=routes)


def make_server(
    service: AccessExecutor, port: int = 0
) -> tuple[uvicorn.Server, socket.socket, str]:
    """port=0 → any free port. We bind the socket OURSELVES and hand it to uvicorn: the card needs the real port
    before the server starts, and keeping the socket open means no other process can grab it in between."""
    sock = socket.socket()
    sock.setsockopt(
        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
    )  # restart right after a stop (like uvicorn does)
    sock.bind(("localhost", port))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(make_app(service, port), log_level="warning")
    )
    return server, sock, f"http://localhost:{port}"


def start(service: AccessExecutor, port: int = 0) -> tuple[uvicorn.Server, str]:
    """Serves the agent in a background thread (eval, tests)."""
    server, sock, url = make_server(service, port)
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [sock]}, daemon=True
    )
    thread.start()
    while (
        not server.started and thread.is_alive()
    ):  # uvicorn starts asynchronously: wait until it listens
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError(f"Access agent failed to start on {url}")
    return server, url


def serve(port: int = PORT) -> None:
    server, sock, url = make_server(AccessExecutor(), port)
    print(f"Access A2A agent on {url}  (card: {AGENT_CARD_WELL_KNOWN_PATH})")
    server.run(sockets=[sock])
