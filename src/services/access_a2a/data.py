"""The IAM team's own data: access requests. It lives with the service, not in the Service Desk —
the only way to read or change it from outside is through the agent (A2A)."""

_SEED = {
    "REQ0001": {
        "email": "joao@company.com", "resource": "Finance BI dashboard", "justification": "monthly report",
        "approver": "marta@company.com", "status": "pending_approval",
    },
}

ACCESS_REQUESTS: dict[str, dict] = {}


def reset() -> None:
    ACCESS_REQUESTS.clear()
    ACCESS_REQUESTS.update({k: dict(v) for k, v in _SEED.items()})


reset()
