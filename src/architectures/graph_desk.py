"""What every graph-based Service Desk shares (module 4): the thread, a turn, confirmations, time travel, costs.

The topologies differ in their NODES and EDGES (handoff.py: agents pass the conversation; supervisor.py: one agent
talks, specialists are its tools). Everything about the STATE's lifecycle is the same, so it lives here once:
- a conversation is a thread (thread_id) in a checkpointer — memory in the eval/tests, SQLite in the chat (4.3);
- a turn is either new input or, when the graph is paused at an interrupt, the user's answer to it (4.4);
- undo() forks from the checkpoint before the last turn (4.3).
"""

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from src.architectures import confirm
from src.auth import Session
from src.core.agent import Agent, ToolCall, Usage, total_usage
from src.tools import run_tool
from src.tools._schema import Tool

FALLBACK = "Sorry, I couldn't complete your request. Please try again."


class GraphDesk:
    entry: str  # the node a new conversation starts at

    def __init__(self, session: Session, registry: dict[str, Tool], verbose: bool, thread_id: str):
        self.session, self.registry, self.verbose = session, registry, verbose
        self.tool_calls: list[ToolCall] = []  # the trace for the eval (observability, not state: not checkpointed)
        self.agents: dict[str, Agent] = {}  # the LIVE objects (clients, counters): rebuilt on every start
        # One conversation = one thread. Without a durable checkpointer (the eval, the tests), it lives in memory.
        self.config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        self._fork_from: RunnableConfig | None = None  # set by undo(): the next turn continues from an OLDER checkpoint
        self.graph: CompiledStateGraph

    def _compile(self, graph, checkpointer: BaseCheckpointSaver | None) -> None:
        self.graph = graph.compile(checkpointer=checkpointer or InMemorySaver())

    # --- One turn ------------------------------------------------------------------------------------------
    def _turn_input(self, user_text: str) -> dict:
        """The input of a new turn: the user's message + this turn's counters back to zero."""
        raise NotImplementedError

    def _clean(self, text: str) -> str:
        """How a saved assistant message is shown to the user (e.g. without the code's signature)."""
        return text

    def reply(self, user_text: str) -> str:
        start = len(self.state.get("messages", []))
        # A confirmation pending → this message IS the answer: resume the paused graph with it (same thread).
        # Otherwise a new turn. durability="sync": each step is on disk BEFORE the next one starts (e.g. before a
        # remote call) — a write per step, nothing next to an LLM call. "exit" would save only at the end.
        turn = Command(resume=user_text) if self.awaiting_confirmation else self._turn_input(user_text)
        self.graph.invoke(turn, self._fork_from or self.config, durability="sync")
        self._fork_from = None  # the new branch is now the thread's latest checkpoint
        answers = [self._clean(m["content"]) for m in self.state["messages"][start:] if m["role"] == "assistant"]
        return "\n\n".join(a for a in answers if a) or FALLBACK

    @property
    def state(self) -> dict:
        """The conversation as the checkpointer has it now (the latest checkpoint of this thread)."""
        return self.graph.get_state(self._fork_from or self.config).values

    @property
    def active(self) -> str:
        return self.state.get("active", self.entry)

    @property
    def awaiting_confirmation(self) -> bool:
        """The graph is paused at an interrupt: the user's next message answers it."""
        return bool(self.graph.get_state(self._fork_from or self.config).interrupts)

    # --- Confirmation (lesson 4.4) -----------------------------------------------------------------------------
    def _hold_for_confirmation(self, name: str, scheduled: dict, tool: str, arguments: dict
                               ) -> tuple[str, bool] | None:
        """A real tool: run it (None), unless it needs the user's confirmation — then hold it and end the turn."""
        if scheduled.get("confirm") or tool not in self.agents[name].allowed_tools:
            return None  # one held call per activation; a tool it doesn't own is refused by run_tool anyway
        if prompt := confirm.prompt_for(self.registry[tool], arguments, self.agents[name].user_texts):
            scheduled["confirm"] = {"agent": name, "tool": tool, "arguments": arguments, "prompt": prompt}
            return confirm.CONFIRM_ASKED, True
        return None

    def _confirmation(self, state: dict) -> tuple[dict, str]:
        """The confirm node's body: PAUSE, then (once, after the answer) run the held call or not.
        Returns (the state update, the outcome for the agent that asked)."""
        action = state["pending"]
        # PAUSE: the checkpoint is saved and reply() returns. Hours later (or after a restart), the user's next
        # message resumes HERE — the node runs again from its first line, so nothing above may have effects.
        answer = interrupt(action["prompt"])
        # --- From here on it runs ONCE, after the answer. -------------------------------------------------------
        tool = self.registry[action["tool"]]
        update = {"messages": [{"role": "user", "content": answer}], "user_texts": [answer], "pending": None}
        if not confirm.is_yes(answer):
            return update, confirm.NOT_CONFIRMED.format(tool=tool.name)
        # The confirmed values ARE now the user's words; run_tool still runs every other check (allowlist, the
        # server's own rules). Only the asking agent's own tools: least privilege survives the pause.
        texts = [*state["user_texts"], answer, *confirm.endorsed(tool, action["arguments"])]
        result, is_error = run_tool(tool.name, action["arguments"], self.session, self.registry,
                                    self.agents[action["agent"]].allowed_tools, texts)
        self.tool_calls.append(ToolCall(tool.name, action["arguments"], result, is_error))
        self._log(f"  🔧 {tool.name}({action['arguments']}) — confirmed by the user")
        return update, confirm.CONFIRMED.format(tool=tool.name, result=result)

    # --- Time travel (lesson 4.3) ----------------------------------------------------------------------------
    def history(self) -> list[str]:
        """The thread's checkpoints, oldest first: one per step (input, each node), as the checkpointer saved them."""
        lines = []
        for snap in reversed(list(self.graph.get_state_history(self.config))):
            messages = snap.values.get("messages", [])
            last = messages[-1]["content"][:60].replace("\n", " ") if messages else ""
            meta = snap.metadata or {}
            lines.append(f"step {meta.get('step', '?'):>3} {meta.get('source', ''):<5} "
                         f"next={','.join(snap.next) or '-':<10} msgs={len(messages):<3} {last}")
        return lines

    def undo(self) -> bool:
        """Forgets the last turn: the next turn continues from the checkpoint BEFORE it (a fork — the history keeps
        both branches, for audit). It rewinds OUR state only: a ticket opened in that turn is still open in the
        ticket system, an A2A task still exists on the IAM side. Time travel undoes memory, not the world."""
        for snap in self.graph.get_state_history(self._fork_from or self.config):  # newest first
            if snap.metadata and snap.metadata.get("source") == "input" and snap.parent_config:
                # An "input" checkpoint holds the state BEFORE that turn's message; its parent = end of the turn before.
                self._fork_from = snap.parent_config
                return True
        return False  # nothing to undo (first turn: there is no "before")

    # --- Accounting (each local agent prices its own model; remote agents cost US$ 0 to US) ---
    @property
    def usage(self) -> Usage:
        return total_usage([a.usage for a in self.agents.values()])

    def cost(self) -> float:
        return sum(a.cost() for a in self.agents.values())

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)
