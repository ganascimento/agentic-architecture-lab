"""The account system's own data. The DIRECTORY itself (who exists, department, manager) is shared company
infrastructure (src/data.py): login, the IAM team and every server read it — none of them owns it."""

PASSWORD_RESETS: list[str] = []  # emails a reset link was sent to


def reset() -> None:
    """Back to the seed (tests, each eval run). Nobody outside the server can call it — on purpose."""
    PASSWORD_RESETS.clear()
