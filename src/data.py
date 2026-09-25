"""Fake in-memory data simulating the company's systems (accounts, user directory, knowledge base,
ticketing, access requests, system status). In later modules this becomes real MCP servers / RAG."""

# Local accounts for the login. ⚠️ Plaintext passwords: acceptable ONLY because this is a study project.
# Real systems store a slow hash (argon2/bcrypt) or, better, delegate login to an IdP (SSO/OIDC) — final phase.
ACCOUNTS = [
    {"username": "ana", "password": "ana123", "email": "ana@company.com"},
    {"username": "joao", "password": "joao123", "email": "joao@company.com"},
    {"username": "carlos", "password": "carlos123", "email": "carlos@company.com"},
    {"username": "marta", "password": "marta123", "email": "marta@company.com"},
]

USERS = {
    "ana@company.com": {"name": "Ana Souza", "department": "Sales", "manager": "carlos@company.com"},
    "joao@company.com": {"name": "João Lima", "department": "Finance", "manager": "marta@company.com"},
    "carlos@company.com": {"name": "Carlos Reis", "department": "Sales", "manager": "board@company.com"},
    "marta@company.com": {"name": "Marta Alves", "department": "Finance", "manager": "board@company.com"},
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
        "tags": ["password", "reset", "forgot", "login", "expired"],
        "content": (
            "The Service Desk can send a password reset link to the user's registered email. "
            "If the account is locked, open a ticket."
        ),
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
    {
        "id": "KB007",
        "title": "SAP slow or unavailable",
        "tags": ["sap", "slow", "unavailable", "erp", "timeout"],
        "content": (
            "First check the system status: if there is an ongoing incident, do NOT open a new ticket — "
            "inform the user and the incident number. Otherwise, clear the SAP GUI cache and try again."
        ),
    },
]

# Known outages. Opening one ticket per affected user would flood L2 (eval case 23).
SYSTEM_STATUS = {
    "vpn": {"status": "operational"},
    "email": {"status": "operational"},
    "sap": {"status": "degraded", "incident": "MAJ-042", "note": "Slowness since 08:00, team working on it."},
}

# Seed data from several users: the agent must only ever show the logged-in user's own records.
_SEED_TICKETS = {
    "INC0001": {
        "email": "ana@company.com", "title": "Outlook crashing on startup",
        "description": "Outlook closes right after opening.", "category": "email",
        "priority": "medium", "status": "open", "comments": [],
    },
    "INC0002": {
        "email": "joao@company.com", "title": "Monitor flickering",
        "description": "External monitor flickers.", "category": "hardware",
        "priority": "low", "status": "in_progress", "comments": ["L2: replacement cable requested."],
    },
}
_SEED_ACCESS_REQUESTS = {
    "REQ0001": {
        "email": "joao@company.com", "resource": "Finance BI dashboard", "justification": "monthly report",
        "approver": "marta@company.com", "status": "pending_approval",
    },
}

# "Tables" the tools fill in at runtime
TICKETS: dict[str, dict] = {}
ACCESS_REQUESTS: dict[str, dict] = {}
PASSWORD_RESETS: list[str] = []  # emails a reset link was sent to


def reset() -> None:
    """Back to the initial state — each eval run starts from the same data."""
    TICKETS.clear()
    TICKETS.update({k: {**v, "comments": list(v["comments"])} for k, v in _SEED_TICKETS.items()})
    ACCESS_REQUESTS.clear()
    ACCESS_REQUESTS.update({k: dict(v) for k, v in _SEED_ACCESS_REQUESTS.items()})
    PASSWORD_RESETS.clear()


reset()
