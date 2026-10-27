"""A tool = DEFINITION (what the LLM sees) + IMPLEMENTATION (what our code runs).

Every implementation receives the Session first, injected by the code — it is NOT in the JSON schema,
so the LLM can't fill it in. That's how "who the user is" stays out of the LLM's hands.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # a type hint only: an MCP server built on these Tools must not load the OpenAI SDK (~4 s)
    from openai.types.chat import ChatCompletionToolParam

NO_ARGS: dict = {"type": "object", "properties": {}}


def definition(name: str, description: str, parameters: dict = NO_ARGS) -> ChatCompletionToolParam:
    """OpenAI tool format. Every provider has its own wrapper, but the 3 pieces are always the same:
    name, description (a prompt: it's how the LLM decides WHEN to use it) and a JSON Schema for the arguments."""
    return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}


@dataclass(frozen=True)
class Tool:
    definition: ChatCompletionToolParam
    run: Callable[..., object]  # run(session, **arguments_from_the_llm)
    # Arguments that must come from the user's own words, verified by the HOST (see provenance.py): only the host
    # has the conversation. A plain list of names, so a server can declare it in the tool's _meta.
    from_user: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return self.definition["function"]["name"]


class ToolUnavailable(Exception):
    """The tool's SYSTEM failed (down, timeout, protocol error) — not a refusal of THIS request.

    Two kinds of failure, two audiences (the same split MCP makes between isError and a JSON-RPC error):
    - a business refusal ("still within its deadline") is for the LLM: it can rephrase, ask, explain;
    - a system failure is for OUR code: the LLM can't fix a server that is down, and if it gets the error as
      text it retries, then makes up an excuse — and nobody on our side ever learns the system is down.
    So run_tool lets this one through, and the outermost layer (chat, eval) decides what to do."""
