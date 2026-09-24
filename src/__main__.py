"""Terminal chat with the agent. Run with: .venv/bin/python -m src"""

from src import data
from src.agent import ServiceDeskAgent


def main() -> None:
    agent = ServiceDeskAgent()
    print(f"Service Desk (single-agent, model {agent.model.name}, reasoning {agent.model.reasoning_effort})")
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
            agent = ServiceDeskAgent()
            print("(new conversation)\n")
            continue
        if text == "/state":
            print("Tickets:", data.TICKETS or "none")
            print("Access requests:", data.ACCESS_REQUESTS or "none", "\n")
            continue

        calls_before, cost_before = agent.usage.calls, agent.usage.cost(agent.model.name)
        answer = agent.reply(text)
        calls = agent.usage.calls - calls_before
        cost = agent.usage.cost(agent.model.name) - cost_before
        print(f"\nagent> {answer}")
        print(f"       [{calls} model calls | US$ {cost:.4f} this turn]\n")


if __name__ == "__main__":
    main()
