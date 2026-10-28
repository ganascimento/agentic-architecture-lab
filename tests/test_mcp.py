"""MCP tests — no LLM: our client (SDK) talking to the REAL servers over HTTP, plus the raw wire (httpx) to see
what the SDK writes and what it enforces for us."""

import asyncio
import time

import httpx
import pytest
from mcp import Client

from src.auth import session_for
from src.config import MCP_SERVERS, mcp_urls
from src.services.mcp_client import MCPClient, connect
from src.services.mcp_servers import server as mcp_server
from src.services.mcp_servers.tickets import data as itsm
from src.tools import merge, run_tool
from src.tools._schema import ToolUnavailable

ANA = session_for("ana@company.com")
JOAO = session_for("joao@company.com")
CARLOS = session_for("carlos@company.com")
META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}


@pytest.fixture(scope="session")
def tickets_url(mcp_url):
    return mcp_urls(mcp_url)["tickets"]


@pytest.fixture(scope="session")
def tickets(tickets_url):
    return MCPClient("tickets", tickets_url)  # discovery only reads; the data is reset before each test (conftest)


def post(url: str, method: str, params: dict, name: str | None = None, version: str = "2026-07-28") -> httpx.Response:
    """One raw 2026-07-28 request: a JSON-RPC body + headers that MIRROR it (version, method, tool name)."""
    headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": version, "Mcp-Method": method}
    if name:
        headers["Mcp-Name"] = name
    return httpx.post(url, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, headers=headers)


def test_discovery_negotiates_the_stateless_version(tickets):
    assert tickets.protocol_version == "2026-07-28"
    assert "ticketing" in (tickets.instructions or "")


def test_each_system_is_its_own_server_and_the_tools_merge(systems):
    # Five servers, one registry: the Service Desk sees 18 tools and doesn't know which server has which.
    assert {"open_ticket", "search_knowledge_base", "get_my_profile", "list_my_devices", "search_catalog"} <= set(systems)
    assert systems["get_ticket_status"].definition["function"]["parameters"]["required"] == ["ticket_id"]


def test_the_chat_knows_every_system_the_servers_publish():
    # Two lists, one per side of the protocol (the host must not import the servers): they must agree.
    assert MCP_SERVERS.keys() == mcp_server.SYSTEMS.keys()


def test_a_tool_name_published_by_two_systems_is_an_error(tickets):
    # Finding (e): a | b would let the second server replace the first one's tool in silence (tool shadowing).
    with pytest.raises(ValueError, match="published by both"):
        merge({"tickets": tickets.tools(), "rogue": {"list_my_tickets": tickets.tools()["list_my_tickets"]}})


def test_identity_travels_in_meta_not_in_the_arguments(tickets):
    # The same call for two users sees two different ticket lists: who is asking comes from the session.
    for session, expected in [(ANA, ["INC0001"]), (JOAO, ["INC0002"])]:
        result = tickets.call_tool("list_my_tickets", {}, session)
        assert [t["ticket"] for t in result.structured_content] == expected


def test_a_business_refusal_is_a_result_the_llm_can_read(tickets):
    # isError=true inside a RESULT (not a JSON-RPC error): the model sees the deadline and can tell the user.
    result = tickets.call_tool("escalate_ticket", {"ticket_id": "INC0002"}, JOAO)
    assert result.is_error is True and "2026-10-02 14:00" in result.content[0].text


def test_an_email_made_up_by_the_llm_is_refused(tickets):
    result = tickets.call_tool("list_my_tickets", {"email": "carlos@company.com"}, ANA)
    assert result.is_error is True


def test_writes_persist_in_the_servers_data(tickets):
    opened = tickets.call_tool("open_ticket", {"title": "VPN error -14", "description": "FortiClient error -14",
                                               "category": "network", "priority": "high"}, ANA)
    ticket_id = opened.structured_content["ticket"]
    assert tickets.call_tool("get_ticket_status", {"ticket_id": ticket_id}, ANA).structured_content["priority"] == "high"


def test_provenance_declared_by_the_server_is_enforced_by_the_host(tickets):
    # The server can't check provenance (it never sees the conversation): it declares the rule in the tool's
    # _meta, and run_tool (host) refuses BEFORE the request is sent — the planted INC0003 comment can't close it.
    registry = tickets.tools()
    assert registry["close_ticket"].from_user == ("resolution",)
    _, is_error = run_tool("close_ticket", {"ticket_id": "INC0003", "resolution": "Battery replaced by the vendor"},
                                CARLOS, user_texts=["qual o status do INC0003?"], registry=registry)
    assert is_error is True and itsm.TICKETS["INC0003"]["status"] == "in_progress"


def test_a_justification_that_only_names_the_item_is_refused_over_mcp(systems):
    # Regression found in the eval (case 42): this rule used a host-side callback that doesn't cross the protocol,
    # so through MCP it passed again. Now the catalog server (which knows what SW004 is) refuses it.
    result, is_error = run_tool("request_catalog_approval", {"item_id": "SW004", "justification": "Quero o Adobe Acrobat Pro."},
                                ANA, user_texts=["quero o Adobe Acrobat Pro"], registry=systems)
    assert is_error is True and "only restates the request" in result


def test_item_name_plus_invented_words_still_pass_run_tool_alone(systems):
    # Module 3's gap (eval case 42): the host no longer knows SW004 is "Adobe Acrobat Pro", so the item's name counts
    # as the user's words and this passes at exactly 50%. run_tool alone STILL accepts it — on purpose: since module 4
    # the desk holds it and asks the user first (tests/test_confirmation.py). The fix is a layer, not this function.
    _, is_error = run_tool("request_catalog_approval",
                           {"item_id": "SW004", "justification": "Solicita Adobe Acrobat Pro (instalação de software novo)."},
                           ANA, user_texts=["quero o Adobe Acrobat Pro"], registry=systems)
    assert is_error is False


# --- System failures go to OUR code, not to the LLM (finding f) ------------------------------------------------
def test_a_protocol_error_is_not_shown_to_the_llm(tickets):
    # Unknown tool = a JSON-RPC error: a bug in the integration, for our code.
    with pytest.raises(ToolUnavailable):
        tickets.call_tool("grant_admin_access", {}, ANA)


def test_a_system_that_is_down_raises_instead_of_becoming_chat():
    server, url = mcp_server.start()
    tools = connect({"tickets": mcp_urls(url)["tickets"]})
    server.should_exit = True  # the ticketing system goes down AFTER discovery
    for _ in range(100):  # wait until the port refuses connections
        try:
            httpx.get(url, timeout=0.1)
            time.sleep(0.05)
        except httpx.TransportError:
            break
    with pytest.raises(ToolUnavailable, match="'tickets' system is unavailable"):
        run_tool("list_my_tickets", {}, ANA, registry=tools)


def test_discovery_fails_loudly_when_the_system_is_unreachable():
    with pytest.raises(ToolUnavailable):
        MCPClient("tickets", "http://127.0.0.1:9/tickets/mcp", timeout=2)


# --- The raw wire: what the SDK writes and enforces -------------------------------------------------------------
def test_raw_http_is_just_json_rpc_with_mirrored_headers(tickets_url):
    response = post(tickets_url, "tools/call",
                    {"name": "list_my_tickets", "arguments": {}, "_meta": {**META, "com.company/user": "ana@company.com"}},
                    name="list_my_tickets")
    assert response.status_code == 200
    assert response.json()["result"]["structuredContent"] == [
        {"ticket": "INC0001", "title": "Outlook crashing on startup", "status": "open", "priority": "medium"}]


def test_a_header_that_contradicts_the_body_is_refused(tickets_url):
    # A gateway authorizes by the header; if the body said otherwise, it could be fooled — so the server checks.
    response = post(tickets_url, "tools/call",
                    {"name": "close_ticket", "arguments": {}, "_meta": META}, name="list_my_tickets")
    assert response.status_code == 400


def test_a_call_without_a_user_is_a_protocol_error(tickets_url):
    response = post(tickets_url, "tools/call", {"name": "list_my_tickets", "arguments": {}, "_meta": META},
                    name="list_my_tickets")
    assert response.json()["error"]["code"] == -32001


def test_every_request_must_carry_its_protocol_version(tickets_url):
    # Stateless: no initialize to remember it from. Lesson 3.2 wrote this check by hand; now the SDK does it.
    response = post(tickets_url, "tools/list", {})
    assert response.json()["error"]["code"] == -32602


def test_unsupported_version_is_refused_with_the_supported_ones(tickets_url):
    old = "2025-01-01"
    response = post(tickets_url, "tools/list",
                    {"_meta": {**META, "io.modelcontextprotocol/protocolVersion": old}}, version=old)
    assert response.json()["error"]["code"] == -32022
    assert "2026-07-28" in response.json()["error"]["data"]["supported"]


def test_a_handshake_era_client_still_works(tickets_url):
    # Interop: most of the market still speaks 2025-11-25 (initialize + session). The SDK serves both eras.
    async def legacy() -> tuple[str, list[str]]:
        async with Client(tickets_url, mode="legacy") as client:
            return client.protocol_version, [t.name for t in (await client.list_tools()).tools]

    version, names = asyncio.run(legacy())
    assert version == "2025-11-25" and "open_ticket" in names
