"""Tool tests — no LLM calls. The deterministic part is tested like regular code."""

import json

from src.tools import run_tool, search_knowledge_base


def test_search_finds_vpn_article():
    result = search_knowledge_base("vpn not connecting")
    assert result[0]["id"] == "KB001"


def test_unknown_user_becomes_error_for_the_llm():
    result, is_error = run_tool("get_user", {"email": "ghost@company.com"})
    assert is_error is True
    assert "not found" in result


def test_access_request_stays_pending_with_manager_as_approver():
    result, is_error = run_tool(
        "create_access_request",
        {"email": "ana@company.com", "resource": "Finance folder", "justification": "monthly closing"},
    )
    assert is_error is False
    payload = json.loads(result)
    assert payload["status"] == "pending_approval"
    assert payload["approver"] == "carlos@company.com"


def test_unknown_tool():
    _, is_error = run_tool("grant_admin_access", {})
    assert is_error is True
