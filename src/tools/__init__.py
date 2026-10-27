"""The host's tool machinery: what an agent may see, how a tool call runs, and how registries are merged.

Since module 3 no company system runs in our process: every tool is DISCOVERED from a system's MCP server
(src/services/mcp_client.py) and arrives here as the same Tool object a local function would be. Not even
listed anywhere: access requests (module 2), the IAM team's agent over A2A.

Key point: the LLM never executes anything. It only *asks* to call a tool, with arguments.
Our code does the executing — which is why we can control what each agent is allowed to do.
"""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING

from src.auth import Session
from src.tools import provenance
from src.tools._schema import Tool, ToolUnavailable

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionToolParam


def merge(registries: Mapping[str, Mapping[str, Tool]]) -> dict[str, Tool]:
    """One registry from several systems ({system: {name: Tool}}). A name published twice is an ERROR.

    A plain `a | b` lets the last one win in silence: a server that publishes `request_password_reset` would
    replace the account system's tool, and the allowlists wouldn't notice — they check NAMES. That's "tool
    shadowing", a known MCP attack. Real hosts also namespace the names per server (Claude Code shows
    `mcp__<server>__<tool>`); failing loudly is the one-line version.
    """
    merged: dict[str, Tool] = {}
    owner: dict[str, str] = {}
    for system, tools in registries.items():
        for name, tool in tools.items():
            if name in merged:
                raise ValueError(f"Tool '{name}' is published by both '{owner[name]}' and '{system}'")
            merged[name], owner[name] = tool, system
    return merged


def tools_for(names: Collection[str], registry: Mapping[str, Tool]) -> list[ChatCompletionToolParam]:
    """Subset of a registry — what one agent is allowed to SEE."""
    return [t.definition for name, t in registry.items() if name in names]


def run_tool(
    name: str, arguments: dict, session: Session, registry: Mapping[str, Tool], allowed: set[str] | None = None,
    user_texts: list[str] | None = None,
) -> tuple[str, bool]:
    """Runs the tool the LLM asked for, as the logged-in user. Returns (result_as_text, is_error).

    Errors don't crash the agent: they go back to the LLM as a normal result starting with "Error:",
    and it decides what to do next (ask the user, try another search...). Except ToolUnavailable: the
    system itself failed, which the LLM can't fix — it goes up to our code (see _schema.py).

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
        problem = provenance.check(arg, str(arguments.get(arg, "")), user_texts or [], request_text)
        if problem:
            return f"Error: {problem}", True
    try:
        return json.dumps(tool.run(session, **arguments), ensure_ascii=False), False
    except ToolUnavailable:
        raise  # the system failed, not the request: not the LLM's to handle
    except Exception as e:  # noqa: BLE001 — any other failure (incl. unexpected arguments) is feedback for the LLM
        return f"Error: {e}", True
