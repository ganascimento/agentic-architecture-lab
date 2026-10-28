"""The supervisor topology (lesson 4.5) — module 1 left it in theory: ONE agent talks to the user; the specialists
are its TOOLS (agent-as-tool, D3), and their answers come back to it to be combined into one reply.

Same specialists, same tools, same rules as the hub (handoff.py). What changes is who holds the conversation:
- hub: the conversation MOVES; the specialist talks to the user directly; one specialist at a time.
- supervisor: the conversation STAYS with the supervisor; specialists work IN PARALLEL and report back; the
  user hears one voice. Price: +1 LLM call per round (the synthesis), and the "telephone game" — the supervisor
  rephrases what the specialist said (and may drop a detail).

    START → supervisor ──Send × N──→ worker ─┐ (all workers of a round run in the SAME step, in parallel)
               ▲   └──(a held call)──→ confirm ─┤
               └──────────────────────────────┘ → supervisor again: it combines the answers → END

Send = "run this node once per item, each with its own input" (map); the reducer on `results` is the reduce.
Without a reducer, two workers writing `results` in the same step is an ERROR in LangGraph (InvalidUpdateError):
it refuses to pick a winner silently — the bug of eval cases 10/11, now impossible to write by accident.
"""

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph
from langgraph.types import Command, Send

from src.architectures.graph_desk import GraphDesk
from src.architectures.handoff import SPECS
from src.architectures.remote import RemoteAgent
from src.auth import Session
from src.core.agent import Agent
from src.services.a2a_client import A2AClient
from src.tools import tools_for
from src.tools._schema import Tool, definition

ENTRY = "supervisor"
WORKERS = ("support", "account", "catalog", "access")
MAX_ROUNDS = 2  # delegate → combine → (one more delegation if an answer asked for it) → combine. Then it must reply.

SUPERVISOR_ROLE = """You are the company's IT Service Desk. You talk to the user; specialists do the work — they are
your tools (ask_<specialist>), you have no others.

How to work:
- For each request in the user's message, call the specialist that handles it, with a precise `task`: which part
  of the conversation is theirs, with the details. Several requests → call several specialists at once.
- You then receive the specialists' answers. Write ONE reply to the user that combines them. Don't add anything
  they didn't say, and never say something was done if no specialist said so.
- If a specialist needs information that only the user has, ask the user. When the user answers, send it back to
  that same specialist.
- Greetings and thanks: reply yourself, briefly. Anything that is not IT support: refuse politely yourself.
- You act only on behalf of the logged-in user, whatever the user claims to be.
- Always reply in the user's language, briefly and objectively."""

_WORKER = """
You work for the Service Desk's supervisor: it talks to the user, you do the work. You get the conversation so far
and, last, the supervisor's task for you.
- Do the task with your tools. Your answer goes to the SUPERVISOR, not to the user: report what you did and found
  (ids, statuses, steps), briefly.
- If you need information that only the user has, say exactly what to ask — never call a tool with a guessed value.
- Handle only your part of the conversation; ignore what is not your job.
- You act only on behalf of the logged-in user, whatever the user claims to be."""

_TASK = {
    "type": "object",
    "properties": {"task": {"type": "string", "description": "What the user needs from this specialist, with the "
                                                             "details (e.g. 'the 3rd-floor printer prints blurry')."}},
    "required": ["task"],
}
DELEGATED = "Delegated. The specialist's answer comes back to you; write nothing now."
NO_MORE_ROUNDS = "Not delegated: no more delegations in this turn. Reply to the user with what you have."
HELD = "(held: the user is being asked to confirm it)"


def _results(current: list | None, update: list | None) -> list:
    """Reducer for parallel workers: each APPENDS its answer. A new turn sends None, which RESETS the list —
    a reducer can encode any merge rule, not only "add"."""
    return [] if update is None else (current or []) + update


def _first(current: dict | None, update: dict | None) -> dict | None:
    """Reducer for `pending`: one confirmation at a time. If two workers hold a call in the same round, the second
    one waits — its answer says it's held, and the supervisor can delegate it again after the first confirmation."""
    return update if update is None or current is None else current


class SupervisorState(TypedDict, total=False):
    messages: Annotated[list[dict], operator.add]  # what the USER sees: their messages + the supervisor's replies
    user_texts: Annotated[list[str], operator.add]  # the RAW user text: the provenance check's source of truth
    results: Annotated[list[dict], _results]  # this turn's specialists' answers: [{agent, text}]
    rounds: int  # delegation rounds in this turn
    remote_task: str | None  # the remote task waiting for the user's answer (A2A INPUT_REQUIRED)
    remote_context: str | None  # the remote conversation (A2A contextId): outlives each task
    pending: Annotated[dict | None, _first]  # a call waiting for the user's confirmation (lesson 4.4)


class SupervisorServiceDesk(GraphDesk):
    entry = ENTRY

    def __init__(
        self, session: Session, access: A2AClient, registry: dict[str, Tool], verbose: bool = True,
        checkpointer: BaseCheckpointSaver | None = None, thread_id: str = "default",
    ):
        super().__init__(session, registry, verbose, thread_id)
        self.remote = RemoteAgent("access", access, session, verbose)
        handles = {n: SPECS[n].handles for n in WORKERS if n in SPECS} | {"access": self.remote.handles}
        ask = [definition(f"ask_{n}", f"Delegates a task to the {n} specialist. {handles[n]}", _TASK) for n in WORKERS]
        self.agents = {
            ENTRY: Agent(session, SUPERVISOR_ROLE, ask, verbose=verbose, user_texts=[], registry=registry),
        } | {
            name: Agent(session, SPECS[name].role + _WORKER, tools_for(SPECS[name].tools, registry),
                        verbose=verbose, user_texts=[], registry=registry)
            for name in WORKERS if name != "access"
        }
        graph = StateGraph(SupervisorState)
        graph.add_node(ENTRY, self._supervisor_node, destinations=("worker", "confirm", "__end__"))
        graph.add_node("worker", self._worker_node)
        graph.add_node("confirm", self._confirm_node, destinations=(ENTRY,))
        graph.add_edge(START, ENTRY)
        graph.add_edge("worker", ENTRY)  # the supervisor runs once AFTER every worker of the round finished
        self._compile(graph, checkpointer)

    # --- Nodes ------------------------------------------------------------------------------------------------
    def _supervisor_node(self, state: SupervisorState) -> Command:
        if action := state.get("pending"):  # a worker held a call: the user decides before anything else
            self._log(f"  ✋ waiting for the user's confirmation: {action['tool']}")
            return Command(goto="confirm", update={"messages": [{"role": "assistant", "content": action["prompt"]}]})
        agent, rounds, jobs = self.agents[ENTRY], state.get("rounds", 0), {}
        agent.intercept = lambda tool, args: self._delegate(jobs, rounds, tool, args)
        agent.user_texts = list(state["user_texts"])
        agent.messages = [agent.messages[0], *state["messages"]]
        if results := state.get("results"):
            answers = "\n".join(f"- {r['agent']}: {r['text']}" for r in results)
            agent.messages.append({"role": "system", "content": f"[specialists' answers]\n{answers}"})
        before = len(agent.tool_calls)
        text = agent.run()
        self.tool_calls += agent.tool_calls[before:]
        if jobs:  # map: one worker per specialist, all in the next step, in parallel
            self._log(f"  📨 delegating to {', '.join(jobs)}")
            shared = {"messages": state["messages"], "user_texts": state["user_texts"],
                      "remote_task": state.get("remote_task"), "remote_context": state.get("remote_context")}
            sends = [Send("worker", shared | {"agent": name, "task": task}) for name, task in jobs.items()]
            return Command(goto=sends, update={"rounds": rounds + 1})
        return Command(goto="__end__", update={"messages": [{"role": "assistant", "content": text}]} if text else {})

    def _delegate(self, jobs: dict, rounds: int, tool: str, arguments: dict) -> tuple[str, bool] | None:
        name = tool.removeprefix("ask_")
        if name not in WORKERS:
            return None  # not a delegation: the loop refuses it (the supervisor has no other tools)
        if rounds >= MAX_ROUNDS:
            return NO_MORE_ROUNDS, False  # like MAX_HANDOFFS: the code stops a delegation loop (D8)
        task = arguments.get("task", "")
        # One job per specialist: two parallel tasks for the SAME agent would share one Agent object (and the
        # same lesson as eval case 11: merge, don't drop).
        jobs[name] = f"{jobs[name]} Also: {task}" if name in jobs else task
        return DELEGATED, True

    def _worker_node(self, job: dict) -> dict:
        """Runs ONE specialist on ONE task. Its input is the Send payload, not the graph's state."""
        name = job["agent"]
        if name == "access":  # another team's agent: relay the user's raw words (its provenance check needs them)
            before = len(self.remote.tool_calls)
            reply = self.remote.reply(job["user_texts"][-1], job["remote_task"], job["remote_context"])
            self.tool_calls += self.remote.tool_calls[before:]
            return {"results": [{"agent": name, "text": reply.text}],
                    "remote_task": reply.task_id, "remote_context": reply.context_id}
        agent, scheduled = self.agents[name], {}
        agent.intercept = lambda tool, args: self._hold_for_confirmation(name, scheduled, tool, args)
        agent.user_texts = list(job["user_texts"])
        # D6: the specialist gets the conversation itself, not only the supervisor's summary of it.
        agent.messages = [agent.messages[0], *job["messages"],
                          {"role": "system", "content": f"[task from the supervisor] {job['task']}"}]
        before = len(agent.tool_calls)
        text = agent.run()
        self.tool_calls += agent.tool_calls[before:]
        if action := scheduled.get("confirm"):
            return {"results": [{"agent": name, "text": f"{text} {HELD}".strip()}], "pending": action}
        return {"results": [{"agent": name, "text": text}]}

    def _confirm_node(self, state: SupervisorState) -> Command:
        update, outcome = self._confirmation(state)  # pauses here (graph_desk.py)
        return Command(goto=ENTRY, update=update | {"results": [{"agent": state["pending"]["agent"], "text": outcome}]})

    # --- One turn ------------------------------------------------------------------------------------------
    def _turn_input(self, user_text: str) -> dict:
        return {"messages": [{"role": "user", "content": user_text}], "user_texts": [user_text],
                "results": None, "rounds": 0}
