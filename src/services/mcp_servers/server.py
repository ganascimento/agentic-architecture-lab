"""The company's systems as MCP servers over HTTP, on the official SDK (lesson 3.3).

One MCP server per SYSTEM, because a server boundary is an OWNERSHIP boundary: each owns its data and its
rules, and the Service Desk can only reach them through the protocol. Five systems, five servers, five URLs:

    tickets    ITSM: incidents, SLA, escalation, closing
    knowledge  KB articles + status page (incidents, maintenance)
    account    the user's own profile and password reset
    assets     CMDB: devices + remote diagnostic
    catalog    software and equipment requests

Transport: Streamable HTTP, spec 2026-07-28. Each request is ONE self-contained POST — no handshake, no session:
the JSON-RPC body (with the version, client capabilities and the user in `params._meta`) plus headers that
MIRROR the body (`MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`), so a gateway or load balancer can route,
rate-limit or authorize by tool WITHOUT parsing JSON. Any instance can answer any request.

What the SDK took over from lesson 3.2's hand-written loop: framing, version negotiation (2026-07-28 AND the
handshake-era 2025-11-25 clients, which is most of the market today), envelope validation, HTTP and its
security headers. What stays OURS (this file): which tools exist, who the call is on behalf of, and the
business-error vs protocol-error split. The business rules stay in each system's tools.py, untouched.

We use the SDK's LOW-LEVEL `Server`, not the decorator-based `MCPServer`: our tools already have a contract
(name, description, JSON Schema in `Tool`), so a generic adapter serves all five. `MCPServer` generates the
schema from type hints — the better fit for a new server written from scratch.

Run (dev):  python -m src.services.mcp_servers     → http://127.0.0.1:8002/<system>/mcp
In dev all five share ONE process and port, mounted at one path each (one terminal instead of five). In
production each team deploys its own server; for the Service Desk only the URLs change (src/config.py).
"""

import contextlib
import json
import socket
import threading
import time
from collections.abc import AsyncGenerator
from types import ModuleType

import mcp_types as types
import uvicorn
from mcp.server.lowlevel.server import Server
from mcp.shared.exceptions import MCPError
from mcp_types.jsonrpc import INVALID_PARAMS
from starlette.applications import Starlette
from starlette.routing import Mount

from src import data  # the company directory (shared infra): which users exist
from src.auth import Session, session_for
from src.services.mcp_servers.account import data as account_data
from src.services.mcp_servers.account import tools as account
from src.services.mcp_servers.assets import tools as assets
from src.services.mcp_servers.catalog import data as catalog_data
from src.services.mcp_servers.catalog import tools as catalog
from src.services.mcp_servers.knowledge import tools as knowledge
from src.services.mcp_servers.tickets import data as tickets_data
from src.services.mcp_servers.tickets import tools as tickets
from src.tools._schema import Tool

PORT = 8002
VERSION = "0.2.0"
SYSTEMS: dict[str, ModuleType] = {  # each module has TOOLS and INSTRUCTIONS
    "tickets": tickets, "knowledge": knowledge, "account": account, "assets": assets, "catalog": catalog,
}

# Our own `_meta` keys. MCP lets anyone add keys under a reverse-DNS prefix ("io.modelcontextprotocol/" is the
# spec's); the receiver is free to ignore what it doesn't know.
USER_KEY = "com.company/user"            # on whose behalf the request is (request _meta, written by the host's CODE)
FROM_USER_KEY = "com.company/fromUser"   # arguments that must be the user's own words (tool _meta, a declaration)
UNAUTHORIZED = -32001  # ours: -32000..-32099 is JSON-RPC's implementation-defined range


def reset() -> None:
    """Every system with writable data back to its seed (tests, each eval run: the servers run in THEIR process)."""
    for system_data in (tickets_data, account_data, catalog_data):  # knowledge and assets are read-only
        system_data.reset()


def _mcp_tool(tool: Tool) -> types.Tool:
    """Our Tool → MCP's tool shape. Same 3 pieces as function calling (name, description, schema), other names."""
    fn = tool.definition["function"]
    # The rule "this argument must come from the user" needs the CONVERSATION, which a server never sees.
    # So it can only declare it; the host enforces it (src/tools/__init__.py: run_tool). Weak spot: tickets/tools.py.
    meta = {FROM_USER_KEY: list(tool.from_user)} if tool.from_user else None
    return types.Tool(name=fn["name"], description=fn["description"], input_schema=dict(fn["parameters"]),
                      _meta=meta)


def _on_behalf_of(meta: dict | None) -> Session:
    """WHO the call is for. Never a tool argument (the LLM fills those in): request metadata, set by the host's code.

    ⚠️ NAIVE, and over HTTP that's now a real hole: the server believes whatever email arrives, so ANYONE who can
    reach the port can act as anyone ({"com.company/user": "bruno@company.com"}). Over stdio (lesson 3.2) only
    the parent process could write to the server. Mitigation for now: listen on 127.0.0.1 only. The fix is the
    same as D10 (a token signed by the caller, verified BEFORE the protocol) — lesson 3.5.
    """
    email = (meta or {}).get(USER_KEY)
    if email not in data.USERS:
        raise MCPError(UNAUTHORIZED, "Unknown or missing user in _meta")
    return session_for(email)


def _result(value: object = None, error: str | None = None) -> types.CallToolResult:
    if error is not None:
        # A business refusal: a RESULT the model reads ("still within its deadline"), not a protocol error.
        return types.CallToolResult(content=[types.TextContent(type="text", text=error)], is_error=True)
    # Two copies of the same answer: text for a model to read, structuredContent for code to parse.
    text = json.dumps(value, ensure_ascii=False)
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], structured_content=value)


def mcp_server(name: str, system: ModuleType) -> Server:
    """One system's tools → one MCP server. Generic: the same adapter serves all five."""
    tools: list[Tool] = system.TOOLS
    by_name = {t.name: t for t in tools}

    async def list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[_mcp_tool(t) for t in tools])

    async def call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        tool = by_name.get(params.name)
        if tool is None:  # a protocol error (for the client's code): it asked for something we never listed
            raise MCPError(INVALID_PARAMS, f"Unknown tool: {params.name}")
        session = _on_behalf_of(ctx.meta)
        try:
            # Sync business code inside an async handler: it blocks the event loop while it runs. Fine here (every
            # tool is in-memory and instant) — and it even serializes the writes to the in-memory tables. A slow
            # tool (a real remote diagnostic) would go to a thread (anyio.to_thread) and then need locking.
            return _result(tool.run(session, **(params.arguments or {})))
        except Exception as e:  # noqa: BLE001 — incl. arguments the LLM made up (TypeError): the model must SEE it
            return _result(error=str(e))

    return Server(name, version=VERSION, instructions=system.INSTRUCTIONS,
                  on_list_tools=list_tools, on_call_tool=call_tool)


def make_app() -> Starlette:
    """All five servers in one ASGI app, one path each: /tickets/mcp, /knowledge/mcp, ..."""
    servers = [mcp_server(name, system) for name, system in SYSTEMS.items()]
    # json_response: a plain JSON answer instead of an SSE stream — enough while no tool streams progress (3.4).
    # stateless_http: no Mcp-Session-Id for the handshake-era clients either (the 2026-07-28 ones never have one).
    apps = {s.name: s.streamable_http_app(stateless_http=True, json_response=True) for s in servers}

    @contextlib.asynccontextmanager
    async def lifespan(_) -> AsyncGenerator[None]:
        # Starlette doesn't run a MOUNTED app's startup: each server's request manager must be started here.
        async with contextlib.AsyncExitStack() as stack:
            for server in servers:
                await stack.enter_async_context(server.session_manager.run())
            yield

    return Starlette(routes=[Mount(f"/{name}", app) for name, app in apps.items()], lifespan=lifespan)


def make_server(port: int = PORT) -> tuple[uvicorn.Server, socket.socket, str]:
    # 127.0.0.1 only (see _on_behalf_of). The SDK adds DNS-rebinding protection for localhost by itself: it
    # refuses requests whose Host/Origin header isn't localhost — a web page can't use the browser to reach us.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # restart right after a stop (like uvicorn does)
    sock.bind(("127.0.0.1", port))
    server = uvicorn.Server(uvicorn.Config(make_app(), log_level="warning"))
    return server, sock, f"http://127.0.0.1:{sock.getsockname()[1]}"


def start(port: int = 0) -> tuple[uvicorn.Server, str]:
    """Serves every system in a background thread (eval, tests). Returns the base URL."""
    server, sock, url = make_server(port)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    while not server.started and thread.is_alive():  # uvicorn starts asynchronously: wait until it listens
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError(f"MCP servers failed to start on {url}")
    return server, url


def serve(port: int = PORT) -> None:
    server, sock, url = make_server(port)
    for name in SYSTEMS:
        print(f"MCP server '{name}' on {url}/{name}/mcp")
    server.run(sockets=[sock])
