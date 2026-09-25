"""A tool = DEFINITION (what the LLM sees) + IMPLEMENTATION (what our code runs).

Every implementation receives the Session first, injected by the code — it is NOT in the JSON schema,
so the LLM can't fill it in. That's how "who the user is" stays out of the LLM's hands.
"""

from collections.abc import Callable
from dataclasses import dataclass

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
    # Arguments that must come from the user's own words, verified by code (see provenance.py).
    from_user: tuple[str, ...] = ()

    @property
    def name(self) -> str:
        return self.definition["function"]["name"]
