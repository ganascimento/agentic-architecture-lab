"""The ticketing system as an MCP server — HAND-WRITTEN, stdlib only (lesson 3.2). Lesson 3.3 moves it to the SDK.

What an MCP server is, stripped down: a loop that reads JSON-RPC 2.0 requests and answers them. Three methods
are enough for tools (spec 2026-07-28, the stateless revision):

    server/discover  → "what do you support?"  (protocol versions, capabilities, instructions)
    tools/list       → "what can you do?"      (name + description + JSON Schema, per tool)
    tools/call       → "do it"                 (name + arguments → content blocks, isError)

Transport: stdio. The host starts this as a CHILD PROCESS and talks over its stdin/stdout, one JSON message
per line. stdout is the protocol's: anything else printed there corrupts it — logs go to stderr.

STATELESS: there is no handshake and no session. Every request carries its own context in `params._meta`
(protocol version, client capabilities). In the previous revisions the client sent `initialize` once and the
server remembered the answer — a state that forced sticky sessions behind a load balancer. Now any request
can go to any server instance.

Two errors, two audiences (the spec's rule):
- a JSON-RPC ERROR is for the CLIENT's code: malformed request, unknown method/tool, wrong version, no identity;
- a RESULT with isError=true is for the LLM: a business refusal ("still within its deadline") it can read
  and react to. Raising those as protocol errors would hide them from the model.

Run by hand (type a JSON line, read a JSON line):  python -m src.services.tickets_mcp
"""

import json
import sys
from typing import IO

from src import data  # the company directory (shared infra): which users exist
from src.auth import session_for
from src.services.tickets_mcp.tools import TOOLS

PROTOCOL_VERSION = "2026-07-28"
SERVER_INFO = {"name": "tickets", "version": "0.1.0"}
INSTRUCTIONS = "The company's ticketing system (ITSM): incidents opened by employees, with SLA and escalation."

# Our own `_meta` keys. MCP lets anyone add keys under a reverse-DNS prefix ("io.modelcontextprotocol/" is the
# spec's); the receiver is free to ignore what it doesn't know.
USER_KEY = "com.company/user"            # on whose behalf the request is (request _meta, written by the host's CODE)
FROM_USER_KEY = "com.company/fromUser"   # arguments that must be the user's own words (tool _meta, a declaration)

# JSON-RPC error codes: the standard ones + MCP's + ours (-32000..-32099 is the implementation-defined range).
PARSE_ERROR, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32601, -32602
UNSUPPORTED_PROTOCOL_VERSION = -32022
UNAUTHORIZED = -32001

_TOOLS = {t.name: t for t in TOOLS}


class ProtocolError(Exception):
    def __init__(self, code: int, message: str, data: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data


def _mcp_tool(tool) -> dict:
    """Our Tool → MCP's tool shape. Same 3 pieces as function calling (name, description, schema), other names."""
    fn = tool.definition["function"]
    result = {"name": fn["name"], "description": fn["description"], "inputSchema": fn["parameters"]}
    if tool.from_user:
        # The rule "this argument must come from the user" needs the CONVERSATION, which this server never sees.
        # So it can only declare it; the host enforces it (src/tools/__init__.py: run_tool). A weak spot: see tools.py.
        result["_meta"] = {FROM_USER_KEY: list(tool.from_user)}
    return result


def _check_meta(params: dict) -> dict:
    """Every request must say which protocol version it speaks — there's no handshake to remember it from."""
    meta = params.get("_meta")
    if not isinstance(meta, dict) or "io.modelcontextprotocol/protocolVersion" not in meta \
            or "io.modelcontextprotocol/clientCapabilities" not in meta:
        raise ProtocolError(INVALID_PARAMS, "Missing _meta protocolVersion/clientCapabilities")
    version = meta["io.modelcontextprotocol/protocolVersion"]
    if version != PROTOCOL_VERSION:
        raise ProtocolError(UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version",
                            {"supported": [PROTOCOL_VERSION], "requested": version})
    return meta


def _on_behalf_of(meta: dict):
    """WHO the call is for. Never a tool argument (the LLM fills those in): request metadata, set by the host's code.

    ⚠️ NAIVE on purpose, like lesson 2.2's header: the server believes whatever email arrives. Over stdio that's
    tolerable — only the parent process can write to our stdin, so "anyone who can send a request" = the host.
    Over HTTP it would be impersonation for anyone who can reach the port. The fix is the same as D10 (a token
    signed by the caller, verified before the protocol) — lesson 3.5.
    """
    email = meta.get(USER_KEY)
    if email not in data.USERS:
        raise ProtocolError(UNAUTHORIZED, "Unknown or missing user in _meta")
    return session_for(email)


def _call_tool(params: dict, meta: dict) -> dict:
    tool = _TOOLS.get(params.get("name", ""))
    if tool is None:
        raise ProtocolError(INVALID_PARAMS, f"Unknown tool: {params.get('name')}")
    session = _on_behalf_of(meta)
    try:
        # Unexpected arguments (e.g. an "email" the LLM made up) fail here with a TypeError → isError for the LLM.
        value = tool.run(session, **params.get("arguments", {}))
    except Exception as e:  # noqa: BLE001 — a business refusal: the model must SEE it to react
        return {"resultType": "complete", "content": [{"type": "text", "text": str(e)}], "isError": True}
    # Two copies of the same answer: text for a model to read, structuredContent for code to parse.
    text = json.dumps(value, ensure_ascii=False)
    return {"resultType": "complete", "content": [{"type": "text", "text": text}], "structuredContent": value,
            "isError": False}


def handle(request: dict) -> dict | None:
    """One JSON-RPC message in → one response out (None for a notification: no id, no answer)."""
    if "id" not in request:
        return None
    try:
        params = request.get("params") or {}
        meta = _check_meta(params)
        method = request.get("method")
        if method == "server/discover":
            result = {
                "resultType": "complete", "supportedVersions": [PROTOCOL_VERSION],
                "capabilities": {"tools": {}}, "instructions": INSTRUCTIONS,
                "_meta": {"io.modelcontextprotocol/serverInfo": SERVER_INFO},
            }
        elif method == "tools/list":
            result = {"resultType": "complete", "tools": [_mcp_tool(t) for t in TOOLS]}
        elif method == "tools/call":
            result = _call_tool(params, meta)
        else:
            raise ProtocolError(METHOD_NOT_FOUND, f"Method not found: {method}")
        return {"jsonrpc": "2.0", "id": request["id"], "result": result}
    except ProtocolError as e:
        error = {"code": e.code, "message": e.message} | ({"data": e.data} if e.data else {})
        return {"jsonrpc": "2.0", "id": request["id"], "error": error}


def serve(stdin: IO[str] = sys.stdin, stdout: IO[str] = sys.stdout) -> None:
    """Until stdin closes (= the host is gone, which also stops this process): read a line, answer a line."""
    for line in stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": PARSE_ERROR, "message": "Parse error"}}
        else:
            response = handle(request)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()  # a pipe is buffered: without this the host waits forever for the answer
