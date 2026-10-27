"""Terminal chat with the Service Desk.

Run (three terminals):  python -m src.services.access_a2a     ← the IAM team's Access agent (A2A service)
                        python -m src.services.mcp_servers    ← the company's systems (5 MCP servers, HTTP)
                        python -m src                         ← the Service Desk
Test accounts are in src/data.py (e.g. ana / ana123).
"""

import getpass

from a2a.client import AgentCardResolutionError

from src.architectures import service_desk
from src.auth import Session, login
from src.config import ACCESS_AGENT_URL, MCP_SERVERS
from src.services.mcp_client import connect
from src.tools._schema import Tool, ToolUnavailable


def main() -> None:
    # Login first: from here on, WHO the user is comes from this session — nothing typed in the chat changes it.
    session = None
    while session is None:
        session = login(input("username: ").strip(), getpass.getpass("password: "))
        if session is None:
            print("Invalid credentials.\n")

    # The company's systems: discovered once (their tools), reused by every conversation (/new).
    try:
        tools = connect(MCP_SERVERS)
    except ToolUnavailable as e:
        print(f"\n{e}. Start the systems: python -m src.services.mcp_servers")
        return
    chat(session, tools)


def chat(session: Session, tools: dict[str, Tool]) -> None:
    try:
        desk = service_desk(session, tools)
    except AgentCardResolutionError:  # discovery failed: the card is unreachable
        print(f"\nThe Access agent is not reachable at {ACCESS_AGENT_URL}. Start it: python -m src.services.access_a2a")
        return
    print(f"\nService Desk — logged in as {session.name} <{session.email}>")
    print("Commands: /new (new conversation), /quit\n")

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
            desk = service_desk(session, tools)
            print("(new conversation)\n")
            continue

        calls_before, cost_before = desk.usage.calls, desk.cost()
        try:
            answer = desk.reply(text)
        except ToolUnavailable as e:  # a system is down: OUR message, not an excuse made up by the LLM
            print(f"\nagent> Sorry, a system I need is unavailable right now. Please try again later.\n       [{e}]\n")
            continue
        print(f"\nagent> {answer}")
        print(f"       [{desk.usage.calls - calls_before} model calls | US$ {desk.cost() - cost_before:.4f} this turn]\n")


if __name__ == "__main__":
    main()
