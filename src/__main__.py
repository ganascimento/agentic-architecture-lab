"""Terminal chat with the Service Desk.

Run (two terminals):  python -m src.services.access_a2a     ← the IAM team's Access agent (A2A service)
                      python -m src                         ← the Service Desk (starts the tickets MCP server itself)
Test accounts are in src/data.py (e.g. ana / ana123).
"""

import getpass

from a2a.client import AgentCardResolutionError

from src import data
from src.architectures import service_desk
from src.auth import Session, login
from src.config import ACCESS_AGENT_URL, TICKETS_MCP_COMMAND
from src.services.mcp_client import MCPClient


def main() -> None:
    # Login first: from here on, WHO the user is comes from this session — nothing typed in the chat changes it.
    session = None
    while session is None:
        session = login(input("username: ").strip(), getpass.getpass("password: "))
        if session is None:
            print("Invalid credentials.\n")

    # The ticketing system's MCP server: a child process (stdio) that lives as long as this chat — /new starts a
    # new conversation, not a new ticketing system. Closing the client ends the server.
    with MCPClient(TICKETS_MCP_COMMAND) as tickets:
        chat(session, tickets)


def chat(session: Session, tickets: MCPClient) -> None:
    try:
        desk = service_desk(session, tickets)
    except AgentCardResolutionError:  # discovery failed: the card is unreachable
        print(f"\nThe Access agent is not reachable at {ACCESS_AGENT_URL}. Start it: python -m src.services.access_a2a")
        return
    print(f"\nService Desk — logged in as {session.name} <{session.email}>")
    print("Commands: /new (new conversation), /state (catalog requests, password resets), /quit\n")

    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text == "/quit":
            break
        if text == "/new":
            desk = service_desk(session, tickets)
            print("(new conversation)\n")
            continue
        if text == "/state":
            # Only what lives in OUR process. Access requests (IAM, A2A) and tickets (MCP server) live in other
            # processes now — ask the agent ("my tickets", "my access requests").
            print("Catalog requests:", data.CATALOG_REQUESTS or "none")
            print("Password resets:", data.PASSWORD_RESETS or "none", "\n")
            continue

        calls_before, cost_before = desk.usage.calls, desk.cost()
        answer = desk.reply(text)
        print(f"\nagent> {answer}")
        print(f"       [{desk.usage.calls - calls_before} model calls | US$ {desk.cost() - cost_before:.4f} this turn]\n")


if __name__ == "__main__":
    main()
