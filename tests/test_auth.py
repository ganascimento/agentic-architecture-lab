"""Login tests — no LLM calls."""

from src.auth import login


def test_valid_login_returns_session():
    session = login("ana", "ana123")
    assert session is not None
    assert session.email == "ana@company.com"


def test_wrong_password_is_refused():
    assert login("ana", "wrong") is None


def test_unknown_user_is_refused():
    assert login("ghost", "ana123") is None
