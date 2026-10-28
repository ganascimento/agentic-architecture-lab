"""Terminal chat with the Service Desk.

Run (three terminals):  python -m src.services.access_a2a     ← the IAM team's Access agent (A2A service)
                        python -m src.services.mcp_servers    ← the company's systems (5 MCP servers, HTTP)
                        python -m src                         ← the Service Desk
Test accounts are in src/data.py (e.g. ana / ana123).

Since module 4 the conversations are saved (.state/service_desk.sqlite): quit, run again, log in — and the
conversation continues where it stopped. /history shows the saved steps; /undo forgets the last turn.
Managers decide access requests with /approvals, /approve <id>, /reject <id> — commands, never the chat (D2).
"""

import getpass

from a2a.client import AgentCardResolutionError

from src import conversations
from src.architectures import service_desk
from src.auth import Session, login
from src.config import ACCESS_AGENT_URL, MCP_SERVERS, TOPOLOGY
from src.services.a2a_client import A2AClient
from src.services.iam_approvals import ApprovalsClient
from src.services.mcp_client import connect
from src.tools._schema import Tool, ToolUnavailable

COMMANDS = ("/new (new conversation), /threads, /open <n>, /history, /undo (forget the last turn), "
            "/approvals, /approve <id>, /reject <id>, /quit")


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
        access = A2AClient(ACCESS_AGENT_URL)  # discovery: reading the Access agent's card
    except AgentCardResolutionError:  # discovery failed: the card is unreachable
        print(f"\nThe Access agent is not reachable at {ACCESS_AGENT_URL}. Start it: python -m src.services.access_a2a")
        return
    store = conversations.open_store()
    approvals = ApprovalsClient(ACCESS_AGENT_URL, access.credentials.audience)

    def open_thread(number: int):
        # The thread id is built by the CODE from the session: "/open 2" can only open one of YOUR conversations.
        return service_desk(session, tools, access=access, checkpointer=store,
                            thread_id=conversations.thread_id(session, number))

    mine = conversations.threads_of(store, session)
    number = mine[-1] if mine else 1
    desk = open_thread(number)
    print(f"\nService Desk ({TOPOLOGY}) — logged in as {session.name} <{session.email}>")
    if saved := desk.state.get("messages"):
        print(f"(continuing conversation #{number}: {len(saved)} messages saved — /new starts another)")
        print(f"last reply: {saved[-1]['content'][:200]}")
    print(f"Commands: {COMMANDS}\n")

    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        command, _, argument = text.partition(" ")
        if command == "/quit":
            break
        if command == "/new":
            number = max(conversations.threads_of(store, session), default=0) + 1
            desk = open_thread(number)
            print(f"(new conversation #{number})\n")
            continue
        if command == "/threads":
            for n in conversations.threads_of(store, session):
                print(f"  {'*' if n == number else ' '} #{n}  {conversations.title(store, session, n)}")
            print()
            continue
        if command == "/open":
            if argument.isdigit() and int(argument) in conversations.threads_of(store, session):
                number = int(argument)
                desk = open_thread(number)
                print(f"(conversation #{number}, agent: {desk.active})\n")
            else:
                print("(no such conversation — see /threads)\n")
            continue
        if command == "/history":
            print("\n".join(desk.history()) + "\n")
            continue
        if command == "/approvals":  # the logged-in manager's queue, straight from the IAM service
            pending = approvals.pending(session)
            for r in pending:
                print(f"  {r['request']}  {r['requester']}  {r['resource']}  — \"{r['justification']}\"")
            print("  (nothing waiting for you)\n" if not pending else "")
            continue
        if command in ("/approve", "/reject") and argument:
            _, message = approvals.decide(session, argument.strip(), approve=command == "/approve")
            print(f"  {message}\n")
            continue
        if command == "/undo":
            print("(last turn forgotten — tickets or requests it created still exist)\n" if desk.undo()
                  else "(nothing to undo)\n")
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
