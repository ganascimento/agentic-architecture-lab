"""Terminal chat with the Service Desk.

Run with:  python -m src                  (single agent)
           python -m src --arch handoff   (single | routing | handoff)
Test accounts are in src/data.py (e.g. ana / ana123).
"""

import argparse
import getpass

from src import data
from src.architectures import ARCHITECTURES
from src.auth import login


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", choices=ARCHITECTURES, default="handoff")
    args = parser.parse_args()

    # Login first: from here on, WHO the user is comes from this session — nothing typed in the chat changes it.
    session = None
    while session is None:
        session = login(input("username: ").strip(), getpass.getpass("password: "))
        if session is None:
            print("Invalid credentials.\n")

    new_desk = lambda: ARCHITECTURES[args.arch](session, True)
    desk = new_desk()
    print(
        f"\nService Desk ({args.arch}) — logged in as {session.name} <{session.email}>"
    )
    print("Commands: /new (new conversation), /state (tickets and requests), /quit\n")

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
            desk = new_desk()
            print("(new conversation)\n")
            continue
        if text == "/state":
            print("Tickets:", data.TICKETS or "none")
            print("Access requests:", data.ACCESS_REQUESTS or "none")
            print("Password resets:", data.PASSWORD_RESETS or "none", "\n")
            continue

        calls_before, cost_before = desk.usage.calls, desk.cost()
        answer = desk.reply(text)
        print(f"\nagent> {answer}")
        print(
            f"       [{desk.usage.calls - calls_before} model calls | US$ {desk.cost() - cost_before:.4f} this turn]\n"
        )


if __name__ == "__main__":
    main()
