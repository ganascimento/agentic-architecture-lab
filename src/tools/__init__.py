"""Tool registry. One module per company "system" (in module 3 each one becomes an MCP server).

Key point: the LLM never executes anything. It only *asks* to call a tool, with arguments.
Our code does the executing — which is why we can control what each agent is allowed to do.
"""

import json
from collections.abc import Collection

from openai.types.chat import ChatCompletionToolParam

from src.auth import Session
from src.tools import access, account, knowledge, provenance, tickets

_ALL = [*knowledge.TOOLS, *tickets.TOOLS, *access.TOOLS, *account.TOOLS]
REGISTRY = {t.name: t for t in _ALL}
TOOLS: list[ChatCompletionToolParam] = [t.definition for t in _ALL]  # everything (the single agent)


def tools_for(names: Collection[str]) -> list[ChatCompletionToolParam]:
    """Subset of TOOLS — what one specialist is allowed to SEE."""
    return [t.definition for t in _ALL if t.name in names]


def run_tool(
    name: str, arguments: dict, session: Session, allowed: set[str] | None = None, user_texts: list[str] | None = None,
) -> tuple[str, bool]:
    """Runs the tool the LLM asked for, as the logged-in user. Returns (result_as_text, is_error).

    Errors don't crash the agent: they go back to the LLM as a normal result starting with "Error:",
    and it decides what to do next (ask the user, try another search...).

    `allowed` is the real least-privilege lock: hiding a tool from the LLM is not enough, because it can
    still ASK for any name (hallucination, prompt injection). The code refuses what the agent doesn't own.

    `user_texts` are the RAW user messages, kept by the code: the source of truth for arguments that must
    come from the user. Fail-closed: no user_texts → those arguments can't be verified → refused.
    """
    if allowed is not None and name not in allowed:
        return f"Error: tool '{name}' is not available to this agent.", True
    tool = REGISTRY.get(name)
    if tool is None:
        return f"Unknown tool: {name}", True
    for arg in tool.from_user:
        # The other arguments ARE the request (e.g. the resource): their words don't prove anything.
        request_text = " ".join(str(v) for k, v in arguments.items() if k != arg)
        problem = provenance.check(arg, str(arguments.get(arg, "")), user_texts or [], request_text)
        if problem:
            return f"Error: {problem}", True
    try:
        return json.dumps(tool.run(session, **arguments), ensure_ascii=False), False
    except Exception as e:  # noqa: BLE001 — any failure (incl. unexpected arguments) becomes feedback for the LLM
        return f"Error: {e}", True
