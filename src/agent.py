"""Single-agent Service Desk (baseline).

This file IS the "agent": an LLM + instructions + tools + history, running in a loop.
No framework. Everything LangGraph, CrewAI etc. do is a variation of this loop.
"""

import json
from dataclasses import dataclass

from openai import OpenAI, omit
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from src.config import AGENT, PRICES, ModelConfig
from src.tools import TOOLS, run_tool

SYSTEM_PROMPT = """You are the IT Service Desk support agent for the company.

How to work:
- One message may contain more than one problem. Handle each one separately.
- For technical problems, search the knowledge base before giving guidance and follow the official procedure.
- Before opening a ticket or an access request, identify the user by corporate email.
  If you don't know the email, ask for it.
- Open a ticket when the article says so, or when the user says they already tried the procedure without success.
- Access requests: register the request with a justification. Make it clear that access depends on
  the manager's approval — never say access has been granted.
- Always reply in the user's language, briefly and objectively."""


@dataclass
class ToolCall:
    """One tool execution — recorded so the eval can check WHAT the agent did, not just what it said."""
    name: str
    arguments: dict
    result: str
    is_error: bool


@dataclass
class Usage:
    """Accumulates tokens and model calls — the basis for comparing architectures in lesson 1.3."""
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


class ServiceDeskAgent:
    def __init__(
        self,
        model: ModelConfig = AGENT,
        max_steps: int = 10,
        verbose: bool = True,
        system_prompt: str = SYSTEM_PROMPT,
        tools: list[ChatCompletionToolParam] = TOOLS,
    ):
        # An "agent" here is just configuration on top of a generic loop: model + prompt + tools.
        # The specialists (src/specialists.py) are this same class with another prompt and fewer tools.
        self.client = OpenAI()
        self.model = model
        self.tools = tools
        self.allowed_tools = {t["function"]["name"] for t in tools}
        self.max_steps = max_steps  # Design question #4: who decides it's done? (safety stop)
        self.verbose = verbose
        # The agent's "state" is just this: the conversation history.
        # In the OpenAI API the system prompt is the first message of the list.
        self.messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": system_prompt}]
        self.usage = Usage()
        self.tool_calls: list[ToolCall] = []  # the agent's "trace": every tool it ran, in order

    def reply(self, user_text: str) -> str:
        self.messages.append({"role": "user", "content": user_text})

        # ======================= THE AGENT LOOP =======================
        for _ in range(self.max_steps):
            # 1. Ask the LLM: "given all of this, what's the next step?"
            response = self.client.chat.completions.create(
                model=self.model.name,
                messages=self.messages,
                tools=self.tools,
                reasoning_effort=self.model.reasoning_effort or omit,  # type: ignore[arg-type]
            )
            if response.usage:
                self.usage.add(response.usage)
            choice = response.choices[0]
            message = choice.message

            # 2. Store the response in the history (including tool requests).
            self.messages.append(message.model_dump(exclude_none=True))  # type: ignore[arg-type]

            # 3. Does the LLM want to use tools? We run them and send the results back.
            if choice.finish_reason == "tool_calls" and message.tool_calls:
                for call in message.tool_calls:
                    if call.type != "function":
                        continue
                    arguments = json.loads(call.function.arguments)  # arrives as a JSON string
                    result, is_error = run_tool(call.function.name, arguments, self.allowed_tools)
                    self.tool_calls.append(ToolCall(call.function.name, arguments, result, is_error))
                    self._log(f"  🔧 {call.function.name}({arguments})")
                    self._log(f"     ↳ {'❌ ' if is_error else ''}{result[:200]}")
                    # One "tool" message per call, linked to the request by its id.
                    self.messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
                continue  # back to step 1: the LLM decides what to do with the results

            # 4. Any other finish reason = end of this turn.
            if choice.finish_reason == "content_filter" or message.refusal:
                return "I can't help with that request."
            if choice.finish_reason == "length":
                return "[response cut off: token limit reached]"
            return message.content or ""
        # ==============================================================

        return "[agent stopped: step limit reached]"

    def cost(self) -> float:
        """US$ spent so far. The multi-agent desk has the same method (it sums several models)."""
        return self.usage.cost(self.model.name)

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)
