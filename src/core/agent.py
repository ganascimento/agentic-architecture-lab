"""The generic agent loop: an LLM + instructions + tools + history, running in a loop.

No framework. Everything LangGraph, CrewAI etc. do is a variation of this loop.
An "agent" is just configuration on top of it (model + prompt + tools) — see src/architectures/.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass

from openai import OpenAI, omit
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionMessageToolCallUnion, ChatCompletionToolParam
from openai.types.chat.chat_completion import Choice

from src.auth import Session
from src.config import AGENT, PRICES, ModelConfig
from src.tools import REGISTRY, run_tool
from src.tools._schema import Tool

# One client for the whole process: each OpenAI() opens its own HTTP connection pool (a new TLS handshake
# on every agent's first call). Agents are cheap config objects; the connection is not.
CLIENT = OpenAI()

# A hook for tools the agent's OWNER handles itself (e.g. handoff transfers): given (name, arguments), return
# None to run the tool normally, or (result_for_the_llm, end_turn) to handle it. See architectures/handoff.py.
Intercept = Callable[[str, dict], tuple[str, bool] | None]


@dataclass
class ToolCall:
    """One tool execution — recorded so the eval can check WHAT the agent did, not just what it said."""
    name: str
    arguments: dict
    result: str
    is_error: bool


@dataclass
class Usage:
    """Accumulates tokens and model calls — the basis for comparing architectures."""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, usage) -> None:
        self.calls += 1
        self.input_tokens += usage.prompt_tokens
        self.output_tokens += usage.completion_tokens

    def cost(self, model: str) -> float:
        price_in, price_out = PRICES.get(model, (0.0, 0.0))
        return (self.input_tokens * price_in + self.output_tokens * price_out) / 1_000_000


def total_usage(parts: list[Usage]) -> Usage:
    """Sum of several agents' usage — for desks made of many agents."""
    return Usage(
        calls=sum(u.calls for u in parts),
        input_tokens=sum(u.input_tokens for u in parts),
        output_tokens=sum(u.output_tokens for u in parts),
    )


class Agent:
    def __init__(
        self,
        session: Session,
        system_prompt: str,
        tools: list[ChatCompletionToolParam],
        model: ModelConfig = AGENT,
        max_steps: int = 10,
        verbose: bool = True,
        user_texts: list[str] | None = None,
        intercept: Intercept | None = None,
        registry: dict[str, Tool] = REGISTRY,
    ):
        self.session = session  # who is logged in: passed by the CODE to every tool, never by the LLM
        self.model = model
        self.tools = tools
        self.allowed_tools = {t["function"]["name"] for t in tools}
        self.max_steps = max_steps  # safety stop: who decides it's done?
        self.verbose = verbose
        # The agent's "state" is just this: the conversation history.
        # In the OpenAI API the system prompt is the first message of the list.
        # Telling the LLM who is logged in is INFORMATION (to greet, to reply); the authority is in the tools.
        identity = f"\n\nLogged-in user (from the login, not from the chat): {session.name} <{session.email}>."
        self.messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": system_prompt + identity}]
        self.usage = Usage()
        self.tool_calls: list[ToolCall] = []  # the agent's "trace": every tool call, in order
        # What the user REALLY typed, kept by the code (not by the LLM): the source of truth for the provenance
        # check. A desk that builds the messages itself (the handoff desk) passes its own list and fills it.
        self._owns_user_texts = user_texts is None
        self.user_texts = [] if user_texts is None else user_texts
        self.intercept = intercept
        self.registry = registry  # where its tools come from (the Service Desk's, or another team's service)

    def reply(self, user_text: str) -> str:
        if self._owns_user_texts:
            self.user_texts.append(user_text)
        self.messages.append({"role": "user", "content": user_text})
        return self.run()

    def run(self) -> str:
        """The loop itself, over whatever is in self.messages (the handoff desk fills them before calling)."""
        worked = False    # did a REAL tool run in this call?
        end_turn = False  # did the owner (intercept) ask to end the turn?
        # ======================= THE AGENT LOOP =======================
        for _ in range(self.max_steps):
            # 1-2. Ask the LLM "given all of this, what's the next step?" and store its answer in the history.
            choice = self._ask_llm()
            message = choice.message

            # 3. Does the LLM want to use tools? We run them and send the results back.
            if choice.finish_reason == "tool_calls" and message.tool_calls:
                step_worked, step_end = self._execute_tool_calls(message.tool_calls)
                worked, end_turn = worked or step_worked, end_turn or step_end
                if end_turn and not worked:  # e.g. a pure transfer: nothing to report, end now (saves a call)
                    return message.content or ""
                continue  # back to step 1: the LLM decides what to do with the results

            # 4. Any other finish reason = end of this turn.
            return self._final_text(choice)
        # ==============================================================

        return "[agent stopped: step limit reached]"

    # --- The loop's steps ---------------------------------------------------------------------------

    def _ask_llm(self) -> Choice:
        response = CLIENT.chat.completions.create(
            model=self.model.name,
            messages=self.messages,
            tools=self.tools,
            reasoning_effort=self.model.reasoning_effort or omit,  # type: ignore[arg-type]
        )
        if response.usage:
            self.usage.add(response.usage)
        choice = response.choices[0]
        # The history keeps the LLM's answer too, including its tool requests.
        self.messages.append(choice.message.model_dump(exclude_none=True))  # type: ignore[arg-type]
        return choice

    def _execute_tool_calls(self, calls: list[ChatCompletionMessageToolCallUnion]) -> tuple[bool, bool]:
        """Runs every tool call of one LLM answer. Returns (a real tool ran, the owner asked to end the turn)."""
        worked = end_turn = False
        for call in calls:
            if call.type != "function":
                continue
            name = call.function.name
            arguments = json.loads(call.function.arguments)  # arrives as a JSON string
            handled = self.intercept(name, arguments) if self.intercept else None
            if handled:
                result, stop = handled
                end_turn = end_turn or stop
                self.tool_calls.append(ToolCall(name, arguments, result, False))
                self._log(f"  🔀 {name}({arguments})")
            else:
                result = self._run_tool(name, arguments)
                worked = True
            # One "tool" message per call, linked to the request by its id.
            self.messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        return worked, end_turn

    def _run_tool(self, name: str, arguments: dict) -> str:
        result, is_error = run_tool(name, arguments, self.session, self.allowed_tools, self.user_texts, self.registry)
        self.tool_calls.append(ToolCall(name, arguments, result, is_error))
        self._log(f"  🔧 {name}({arguments})")
        self._log(f"     ↳ {'❌ ' if is_error else ''}{result[:200]}")
        return result

    @staticmethod
    def _final_text(choice: Choice) -> str:
        if choice.finish_reason == "content_filter" or choice.message.refusal:
            return "I can't help with that request."
        if choice.finish_reason == "length":
            return "[response cut off: token limit reached]"
        return choice.message.content or ""

    def cost(self) -> float:
        """US$ spent so far. The multi-agent desks have the same method (they sum several models)."""
        return self.usage.cost(self.model.name)

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)
