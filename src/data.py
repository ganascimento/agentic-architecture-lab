"""Shared company infrastructure: the clock, login accounts and the user directory.

Everything else lives with the system that owns it, in its own server: tickets, knowledge base + status, CMDB,
catalog and account (module 3: src/services/mcp_servers/*/data.py), access requests (module 2, the IAM team's:
src/services/access_a2a/data.py). The directory stays here because NOBODY in this project owns it: login, the
IAM team and every MCP server read it. In a real company it's the IdP/HR system — read through its own API.
"""

from datetime import datetime

# The company clock. FIXED on purpose: SLAs, warranties and device ages depend on "now", and a real clock
# would make tests and evals change from one day to the next. A real system uses the real clock.
NOW = datetime(2026, 9, 30, 10, 0)


def now() -> datetime:
    return NOW


# ---------------------------------------------------------------------------
# Identity: login accounts + company directory
# ---------------------------------------------------------------------------
# Local accounts for the login. ⚠️ Plaintext passwords: acceptable ONLY because this is a study project.
# Real systems store a slow hash (argon2/bcrypt) or, better, delegate login to an IdP (SSO/OIDC) — final phase.
ACCOUNTS = [
    {"username": "ana", "password": "ana123", "email": "ana@company.com"},
    {"username": "joao", "password": "joao123", "email": "joao@company.com"},
    {"username": "carlos", "password": "carlos123", "email": "carlos@company.com"},
    {"username": "marta", "password": "marta123", "email": "marta@company.com"},
    {"username": "pedro", "password": "pedro123", "email": "pedro@company.com"},
    {"username": "bruno", "password": "bruno123", "email": "bruno@company.com"},
]

# `employment` and `department` drive rules enforced by CODE: contractors can only order pre-approved catalog
# items; only the IT department sees internal KB articles (runbooks, admin procedures).
USERS = {
    "ana@company.com": {"name": "Ana Souza", "department": "Sales", "manager": "carlos@company.com",
                        "employment": "employee"},
    "joao@company.com": {"name": "João Lima", "department": "Finance", "manager": "marta@company.com",
                         "employment": "employee"},
    "carlos@company.com": {"name": "Carlos Reis", "department": "Sales", "manager": "board@company.com",
                           "employment": "employee"},
    "marta@company.com": {"name": "Marta Alves", "department": "Finance", "manager": "board@company.com",
                          "employment": "employee"},
    "pedro@company.com": {"name": "Pedro Costa", "department": "Sales", "manager": "carlos@company.com",
                          "employment": "contractor"},
    "bruno@company.com": {"name": "Bruno Tavares", "department": "IT", "manager": "board@company.com",
                          "employment": "employee"},
}
