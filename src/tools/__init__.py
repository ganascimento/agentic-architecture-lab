"""Tool registry: the systems that still run IN our process. One module per company "system".

Key point: the LLM never executes anything. It only *asks* to call a tool, with arguments.
Our code does the executing — which is why we can control what each agent is allowed to do.
"""

from __future__ import annotations

import json
from collections.abc import Collection
from typing import TYPE_CHECKING

from src.auth import Session
from src.tools import account, assets, catalog, knowledge, provenance
from src.tools._schema import Tool

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionToolParam

# The Service Desk's LOCAL systems (function calling, same process). Not here:
# - access requests (module 2): the IAM team's agent, over A2A — nothing in the Service Desk can create one;
# - tickets (module 3): the ticketing system's MCP server — its tools are DISCOVERED at runtime (tools/list) and
#   merged into an agent's registry by the desk (architectures/handoff.py). Same Tool objects, same run_tool.
REGISTRY: dict[str, Tool] = {t.name: t for t in [*knowledge.TOOLS, *account.TOOLS, *assets.TOOLS, *catalog.TOOLS]}


def tools_for(names: Collection[str], registry: dict[str, Tool] = REGISTRY) -> list[ChatCompletionToolParam]:
    """Subset of a registry — what one agent is allowed to SEE."""
    return [t.definition for name, t in registry.items() if name in names]


def run_tool(
    name: str, arguments: dict, session: Session, allowed: set[str] | None = None, user_texts: list[str] | None = None,
    registry: dict[str, Tool] = REGISTRY,
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
    tool = registry.get(name)
    if tool is None:
        return f"Unknown tool: {name}", True
    for arg in tool.from_user:
        # The other arguments ARE the request (e.g. the resource): their words don't prove anything.
        request_text = " ".join(str(v) for k, v in arguments.items() if k != arg)
        if tool.describe_request:
            request_text += " " + tool.describe_request(arguments)
        problem = provenance.check(arg, str(arguments.get(arg, "")), user_texts or [], request_text)
        if problem:
            return f"Error: {problem}", True
    try:
        return json.dumps(tool.run(session, **arguments), ensure_ascii=False), False
    except Exception as e:  # noqa: BLE001 — any failure (incl. unexpected arguments) becomes feedback for the LLM
        return f"Error: {e}", True
