"""Fake in-memory data simulating the company's systems (user directory, knowledge base,
ticketing system). In later modules this becomes real MCP servers / RAG."""

USERS = {
    "ana@company.com": {"name": "Ana Souza", "department": "Sales", "manager": "carlos@company.com"},
    "joao@company.com": {"name": "João Lima", "department": "Finance", "manager": "marta@company.com"},
    "carlos@company.com": {"name": "Carlos Reis", "department": "Sales", "manager": "board@company.com"},
}

KB_ARTICLES = [
    {
        "id": "KB001",
        "title": "VPN won't connect",
        "tags": ["vpn", "network", "forticlient", "connection", "remote"],
        "content": (
            "1. Check that your password hasn't expired (the VPN uses your network password). "
            "2. If you changed your password recently, wait 15 minutes for it to sync. "
            "3. Close and reopen FortiClient; if it persists, reinstall it from the Software Portal. "
            "4. If you see 'error -14', open a ticket for the Network team."
        ),
    },
    {
        "id": "KB002",
        "title": "Forgot password / password expired",
        "tags": ["password", "reset", "locked", "login", "expired"],
        "content": "Use the self-service portal https://password.company.com. If the account is locked, open a ticket.",
    },
    {
        "id": "KB003",
        "title": "Printer printing blurry or failing",
        "tags": ["printer", "printing", "blurry", "toner"],
        "content": "Run the printhead cleaning from the printer panel. If it continues, open a ticket for Hardware.",
    },
    {
        "id": "KB004",
        "title": "Outlook not syncing emails",
        "tags": ["outlook", "email", "e-mail", "sync"],
        "content": "Close Outlook and run 'outlook.exe /resetnavpane'. If that fails, recreate the profile in Control Panel.",
    },
    {
        "id": "KB005",
        "title": "Access to network folders and systems",
        "tags": ["access", "folder", "permission", "system", "grant"],
        "content": (
            "Access requires a formal request with a justification and approval from the direct manager. "
            "The Service Desk registers the request; access is only granted after approval."
        ),
    },
    {
        "id": "KB006",
        "title": "Slow laptop",
        "tags": ["slow", "slowness", "laptop", "freezing", "performance"],
        "content": "Restart the device (many people only suspend it). Check for pending updates. If it persists, open a ticket.",
    },
]

# Pre-existing ticket from another user: the agent must never expose it (see eval case 17).
_SEED_TICKETS = {
    "INC0001": {
        "email": "ana@company.com", "title": "Outlook crashing on startup",
        "description": "Outlook closes right after opening.", "category": "email",
        "priority": "medium", "status": "open",
    },
}

# "Tables" the tools fill in at runtime
TICKETS: dict[str, dict] = {}
ACCESS_REQUESTS: dict[str, dict] = {}


def reset() -> None:
    """Back to the initial state — each eval run starts from the same data."""
    TICKETS.clear()
    TICKETS.update({k: dict(v) for k, v in _SEED_TICKETS.items()})
    ACCESS_REQUESTS.clear()


reset()
