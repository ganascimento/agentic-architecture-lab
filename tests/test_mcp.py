"""MCP tests — no LLM: our hand-written client talking to the REAL tickets server over stdio (a child process)."""

import pytest

from src.auth import session_for
from src.services.mcp_client import MCPError
from src.services.tickets_mcp.server import handle
from src.tools import run_tool

ANA = session_for("ana@company.com")
JOAO = session_for("joao@company.com")
META = {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}


def test_discover_says_what_the_server_supports(tickets):
    assert tickets.server["supportedVersions"] == ["2026-07-28"]
    assert "tools" in tickets.server["capabilities"]


def test_mcp_tools_become_function_calling_tools(tickets):
    # The translation: same name, description and schema — the LLM can't tell the tool is remote.
    tool = tickets.tools()["get_ticket_status"]
    assert tool.definition["type"] == "function"
    assert tool.definition["function"]["parameters"]["required"] == ["ticket_id"]


def test_identity_travels_in_meta_not_in_the_arguments(tickets):
    # The same call for two users sees two different ticket lists: who is asking comes from the session.
    for session, expected in [(ANA, ["INC0001"]), (JOAO, ["INC0002"])]:
        result = tickets.call_tool("list_my_tickets", {}, session)
        assert [t["ticket"] for t in result["structuredContent"]] == expected


def test_a_call_without_a_user_is_a_protocol_error(tickets):
    with pytest.raises(MCPError) as e:
        tickets._request("tools/call", {"name": "list_my_tickets", "arguments": {}})
    assert e.value.code == -32001


def test_a_business_refusal_is_a_result_the_llm_can_read(tickets):
    # isError=true inside a RESULT (not a JSON-RPC error): the model sees the deadline and can tell the user.
    result = tickets.call_tool("escalate_ticket", {"ticket_id": "INC0002"}, JOAO)
    assert result["isError"] is True and "2026-10-02 14:00" in result["content"][0]["text"]


def test_an_email_made_up_by_the_llm_is_refused(tickets):
    result = tickets.call_tool("list_my_tickets", {"email": "carlos@company.com"}, ANA)
    assert result["isError"] is True


def test_unknown_tool_is_a_protocol_error(tickets):
    with pytest.raises(MCPError) as e:
        tickets.call_tool("grant_admin_access", {}, ANA)
    assert e.value.code == -32602


def test_writes_persist_in_the_servers_process(tickets):
    # The data lives in the server: a write through one call is seen by the next one (same process).
    opened = tickets.call_tool("open_ticket", {"title": "VPN error -14", "description": "FortiClient error -14",
                                               "category": "network", "priority": "high"}, ANA)
    ticket_id = opened["structuredContent"]["ticket"]
    status = tickets.call_tool("get_ticket_status", {"ticket_id": ticket_id}, ANA)
    assert status["structuredContent"]["priority"] == "high"


def test_provenance_declared_by_the_server_is_enforced_by_the_host(tickets):
    # The server can't check provenance (it never sees the conversation): it declares the rule in the tool's
    # _meta, and run_tool (host) refuses BEFORE the request is sent — the planted INC0003 comment can't close it.
    registry = tickets.tools()
    assert registry["close_ticket"].from_user == ("resolution",)
    carlos = session_for("carlos@company.com")
    result, is_error = run_tool("close_ticket", {"ticket_id": "INC0003", "resolution": "Battery replaced by the vendor"},
                                carlos, user_texts=["qual o status do INC0003?"], registry=registry)
    assert is_error is True
    status = tickets.call_tool("get_ticket_status", {"ticket_id": "INC0003"}, carlos)
    assert status["structuredContent"]["status"] == "in_progress"


# --- Protocol rules, straight on the handler (no process needed) ------------------------------------------------
def test_every_request_must_carry_its_protocol_version():
    # Stateless revision: no initialize to remember it from.
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert response and response["error"]["code"] == -32602


def test_unsupported_version_is_refused_with_the_supported_ones():
    meta = {**META, "io.modelcontextprotocol/protocolVersion": "2025-06-18"}
    response = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"_meta": meta}})
    assert response and response["error"]["code"] == -32022
    assert response["error"]["data"]["supported"] == ["2026-07-28"]


def test_notifications_get_no_answer_and_unknown_methods_an_error():
    assert handle({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"_meta": META}}) is None
    response = handle({"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {"_meta": META}})
    assert response and response["error"]["code"] == -32601  # we don't offer resources (yet: lesson 3.4)

