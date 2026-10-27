"""MCP client on the official SDK, over Streamable HTTP (lesson 3.3). Lesson 3.2's hand-written stdio client:
see the git history (commit 3f10cec).

The host side of MCP, in three jobs — the same as in 3.2; only the plumbing under them changed:
1. DISCOVER: server/discover (versions, capabilities, instructions) + tools/list (what it can do).
2. TRANSLATE, both ways — the heart of it. MCP does NOT replace function calling:
     tools/list   → our Tool objects → the OpenAI tool format the LLM sees (same 3 pieces: name, description, schema)
     LLM tool_call → tools/call on the server → its result back as a tool message
   The LLM never knows a tool is remote. What changed is WHERE the code runs and WHO owns it.
3. SEPARATE the failures: a business refusal (isError) goes to the LLM; a failure of the SYSTEM (down, timeout,
   protocol error) is ToolUnavailable, for our code (src/tools/_schema.py).

Identity: the user goes in the request's `_meta`, written HERE from the Session — never as a tool argument,
so the LLM can't fill it in (decision D4, now across a network boundary).

Sync facade over an async SDK — like a2a_client.py, and for the same reason: our agent loop is synchronous.
Each call runs in its own event loop (asyncio.run) with its own Client. That works because 2026-07-28 HTTP is
STATELESS: a request is one POST, there is no connection or session to keep alive between calls. (Over stdio
it wouldn't: the server process and the pipes ARE the connection, bound to the loop that started them.)
Cost (measured on WSL): ~50 ms per call, almost all of it building a new httpx client; the tool's own work
on the server is ~1.5 ms. Reusing one client saves only ~4 ms — not worth a loop kept alive in a thread.

Demo (MCP servers running):  python -m src.services.mcp_client
"""

import asyncio
import json
from collections.abc import Coroutine, Mapping
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

import mcp_types as types
from mcp import Client
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

from src.auth import Session
from src.tools import merge
from src.tools._schema import Tool, ToolUnavailable, definition

# The CONTRACT, written on both sides (the servers have their own copy): importing the servers' module here
# would load their code and data into OUR process — exactly what the protocol boundary is for.
USER_KEY = "com.company/user"
FROM_USER_KEY = "com.company/fromUser"
CLIENT_INFO = types.Implementation(name="service-desk", version="0.2.0")
TIMEOUT_SECONDS = 15  # lesson 3.2's readline() waited forever: a hung server hung the whole desk


def _root(e: BaseException) -> BaseException:
    """The SDK runs on task groups: a refused connection arrives wrapped in an ExceptionGroup. Unwrap it."""
    while isinstance(e, BaseExceptionGroup) and len(e.exceptions) == 1:
        e = e.exceptions[0]
    return e


class MCPClient:
    def __init__(self, name: str, url: str, timeout: float = TIMEOUT_SECONDS):
        self.name, self.url, self.timeout = name, url, timeout
        self._mode = "auto"  # first contact: probe server/discover, fall back to the old handshake (initialize)
        self.protocol_version, self.instructions, self._tools = self._sync(self._discover())
        # From now on, adopt the negotiated version directly: no probe per call. A handshake-era server (2025-11-25)
        # would need its initialize on EVERY call (that's what "stateful protocol" costs a stateless client).
        self._mode = self.protocol_version if self.protocol_version in MODERN_PROTOCOL_VERSIONS else "legacy"

    def _client(self) -> Client:
        return Client(self.url, mode=self._mode, client_info=CLIENT_INFO, read_timeout_seconds=self.timeout)

    def _sync(self, coroutine: Coroutine[Any, Any, Any]) -> Any:
        try:
            return asyncio.run(coroutine)
        except Exception as e:  # noqa: BLE001 — business refusals come back as RESULTS; any exception is the system's
            raise ToolUnavailable(f"The '{self.name}' system is unavailable ({_root(e)!r})") from e

    async def _discover(self) -> tuple[str, str | None, list[types.Tool]]:
        async with self._client() as client:
            tools, cursor = [], None
            while True:  # tools/list is paginated: a big server answers in pages
                page = await client.list_tools(cursor=cursor)
                tools += page.tools
                if not (cursor := page.next_cursor):
                    break
            return client.protocol_version, client.instructions, tools

    # --- Protocol --------------------------------------------------------------------------------

    def call_tool(self, name: str, arguments: dict, session: Session) -> types.CallToolResult:
        async def call() -> types.CallToolResult:
            async with self._client() as client:
                return await client.call_tool(name, arguments, meta={USER_KEY: session.email})

        return self._sync(call())

    # --- Translation to OUR tool registry ----------------------------------------------------------

    def tools(self) -> dict[str, Tool]:
        """The server's tools as Tool objects, ready for run_tool: the agent loop needs no change at all.
        Cached since discovery (startup): a tool the server adds later appears on the next start."""
        return {
            t.name: Tool(
                definition(t.name, t.description or "", t.input_schema),
                partial(self._run, t.name),  # a PROXY: same interface as a local function, a tools/call inside
                # The server DECLARES which arguments must be the user's words; WE enforce it (run_tool), because
                # only the host has the conversation. ⚠️ We trust the server's declaration — and the server
                # trusts us to apply it. Another host (e.g. an IDE) may not.
                from_user=tuple((t.meta or {}).get(FROM_USER_KEY, ())),
            )
            for t in self._tools
        }

    def _run(self, name: str, session: Session, **arguments) -> object:
        result = self.call_tool(name, arguments, session)
        text = "\n".join(c.text for c in result.content if isinstance(c, types.TextContent))
        if result.is_error:
            raise ValueError(text)  # run_tool turns it into "Error: ..." for the LLM, like a local tool
        return result.structured_content if result.structured_content is not None else text


def connect(urls: Mapping[str, str]) -> dict[str, Tool]:
    """Discovers every system and merges their tools into ONE registry (a duplicated name fails: see merge).
    In parallel (one thread each, each with its own event loop): startup waits for the slowest server, not the sum."""
    with ThreadPoolExecutor() as pool:
        clients = list(pool.map(MCPClient, urls, urls.values()))
    return merge({client.name: client.tools() for client in clients})


if __name__ == "__main__":
    from src.auth import session_for
    from src.config import MCP_SERVERS

    ana = session_for("ana@company.com")
    tickets = MCPClient("tickets", MCP_SERVERS["tickets"])
    print("negotiated version →", tickets.protocol_version, "| instructions →", tickets.instructions, "\n")
    print("What the LLM sees (function calling):",
          json.dumps(tickets.tools()["escalate_ticket"].definition, indent=2), "\n")
    print("tools/call list_my_tickets as ana →",
          tickets.call_tool("list_my_tickets", {}, ana).model_dump(by_alias=True, exclude_none=True), "\n")
    print("tools/call escalate_ticket(INC0002) as ana (not hers) →",
          tickets.call_tool("escalate_ticket", {"ticket_id": "INC0002"}, ana).model_dump(by_alias=True,
                                                                                        exclude_none=True))
