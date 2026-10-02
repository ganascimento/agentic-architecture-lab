"""MCP client — HAND-WRITTEN over stdio, stdlib only (lesson 3.2). Lesson 3.3 moves it to the SDK.

The host side of MCP, in three jobs:
1. START the server: a child process (stdio transport). It lives as long as this client.
2. DISCOVER: server/discover (versions, capabilities) + tools/list (what it can do).
3. TRANSLATE, both ways — the heart of it. MCP does NOT replace function calling:
     tools/list   → our Tool objects → the OpenAI tool format the LLM sees (same 3 pieces: name, description, schema)
     LLM tool_call → tools/call on the server → its result back as a tool message
   The LLM never knows a tool is remote. What changed is WHERE the code runs and WHO owns it.

Identity: the user goes in the request's `_meta`, written HERE from the Session — never as a tool argument,
so the LLM can't fill it in (decision D4, now across a process boundary).

Demo:  python -m src.services.mcp_client
"""

import json
import subprocess
from functools import partial
from itertools import count

from src.auth import Session
from src.tools._schema import Tool, definition

# The CONTRACT, written on both sides (the server has its own copy): importing the server's module here would load
# its code and data into OUR process — exactly what the protocol boundary is for. Both sides must agree, like
# pinning the a2a-sdk version on both sides in module 2; a mismatch fails loudly (version error, tests).
PROTOCOL_VERSION = "2026-07-28"
USER_KEY = "com.company/user"
FROM_USER_KEY = "com.company/fromUser"
CLIENT_INFO = {"name": "service-desk", "version": "0.1.0"}


class MCPError(Exception):
    """A JSON-RPC error from the server: something for OUR code to fix (not something the LLM can react to)."""

    def __init__(self, code: int, message: str):
        super().__init__(f"MCP error {code}: {message}")
        self.code = code


class MCPClient:
    def __init__(self, command: list[str]):
        # stderr is inherited: the server's logs and tracebacks show up in our terminal, stdout is the protocol.
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                        encoding="utf-8", bufsize=1)
        self._ids = count(1)
        self.server = self._request("server/discover")
        self._tools: list[dict] | None = None

    # --- Protocol --------------------------------------------------------------------------------

    def _request(self, method: str, params: dict | None = None, session: Session | None = None) -> dict:
        """One request, one response. One at a time: the desk is synchronous, so no two calls share the pipe."""
        # Stateless revision: every request says which version it speaks and what the client supports.
        meta = {
            "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
            "io.modelcontextprotocol/clientInfo": CLIENT_INFO,
            "io.modelcontextprotocol/clientCapabilities": {},  # no elicitation, sampling... yet (lesson 3.4)
        }
        if session:
            meta[USER_KEY] = session.email
        request_id = next(self._ids)
        message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": {**(params or {}), "_meta": meta}}
        assert self.process.stdin and self.process.stdout
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()  # ⚠️ no timeout: a hung server hangs us too (the SDK has one)
        if not line:
            raise MCPError(-1, f"server exited (code {self.process.poll()})")
        response = json.loads(line)
        assert response.get("id") == request_id  # one at a time, so the next line IS our answer
        if "error" in response:
            raise MCPError(response["error"]["code"], response["error"]["message"])
        return response["result"]

    def list_tools(self) -> list[dict]:
        # Cached: the list only changes with a new server version. (Real servers say how long to cache it,
        # or notify `list_changed`; a new conversation reading a stale list is the price.)
        tools = self._tools
        if tools is None:
            tools = self._tools = self._request("tools/list")["tools"]
        return tools

    def call_tool(self, name: str, arguments: dict, session: Session) -> dict:
        return self._request("tools/call", {"name": name, "arguments": arguments}, session)

    # --- Translation to OUR tool registry ----------------------------------------------------------

    def tools(self) -> dict[str, Tool]:
        """The server's tools as Tool objects, ready for run_tool: the agent loop needs no change at all."""
        return {
            t["name"]: Tool(
                definition(t["name"], t["description"], t["inputSchema"]),
                partial(self._run, t["name"]),
                # The server DECLARES which arguments must be the user's words; WE enforce it (run_tool), because
                # only the host has the conversation. ⚠️ We trust the server's declaration — and the server
                # trusts us to apply it. Another host (e.g. an IDE) may not.
                from_user=tuple(t.get("_meta", {}).get(FROM_USER_KEY, ())),
            )
            for t in self.list_tools()
        }

    def _run(self, name: str, session: Session, **arguments) -> object:
        result = self.call_tool(name, arguments, session)
        text = "\n".join(c["text"] for c in result["content"] if c["type"] == "text")
        if result.get("isError"):
            raise ValueError(text)  # run_tool turns it into "Error: ..." for the LLM, like a local tool
        return result.get("structuredContent", text)

    def close(self) -> None:
        """Closing stdin = EOF for the server: its loop ends and the process exits."""
        if self.process.poll() is None:
            assert self.process.stdin
            self.process.stdin.close()
            self.process.wait(timeout=5)

    def __enter__(self) -> "MCPClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()


if __name__ == "__main__":
    # Watch the protocol: what the host sends, what the server answers, and what the LLM ends up seeing.
    from src.auth import session_for
    from src.config import TICKETS_MCP_COMMAND

    with MCPClient(TICKETS_MCP_COMMAND) as client:
        print("server/discover →", json.dumps(client.server, indent=2), "\n")
        print("tools/list →", [t["name"] for t in client.list_tools()], "\n")
        print("What the LLM sees (function calling):", json.dumps(client.tools()["escalate_ticket"].definition,
                                                                indent=2), "\n")
        ana = session_for("ana@company.com")
        print("tools/call list_my_tickets as ana →", json.dumps(client.call_tool("list_my_tickets", {}, ana)), "\n")
        print("tools/call escalate_ticket INC0002 as ana (joão's ticket) →",
              json.dumps(client.call_tool("escalate_ticket", {"ticket_id": "INC0002"}, ana)), "\n")
        try:
            client._request("tools/call", {"name": "list_my_tickets", "arguments": {}})  # no user in _meta
        except MCPError as e:
            print("tools/call without a user →", e)
