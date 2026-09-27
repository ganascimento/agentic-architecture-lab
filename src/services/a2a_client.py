"""A minimal A2A client — hand-written with the stdlib (lesson 2.2).

The two things a client does: DISCOVER (read the Agent Card) and SEND (JSON-RPC SendMessage).
It knows nothing about the other agent's prompt, model or tools — only the card and the messages.

Demo (with the server running in another terminal):  python -m src.services.a2a_client
"""

import json
import urllib.request
import uuid

A2A_VERSION = "1.0"


class A2AClient:
    def __init__(self, base_url: str, show_wire: bool = False):
        self.show_wire = show_wire
        self.card = self._http("GET", f"{base_url}/.well-known/agent-card.json")
        self.url = self.card["supportedInterfaces"][0]["url"]  # where to call comes from the card, not config

    def send(self, text: str, user_email: str, task_id: str | None = None, context_id: str | None = None) -> dict:
        """SendMessage (blocking, the default): returns the Task once it's COMPLETED or INPUT_REQUIRED."""
        message = {"messageId": str(uuid.uuid4()), "role": "ROLE_USER", "parts": [{"text": text}]}
        if task_id:
            message["taskId"] = task_id  # continuing an interrupted task (it asked us something)
        if context_id:
            message["contextId"] = context_id
        request = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "SendMessage",
                   # ⚠️ Naive identity (see server.py): replaced by a signed token in lesson 2.5.
                   "params": {"message": message, "metadata": {"userEmail": user_email}}}
        response = self._http("POST", self.url, request)
        if "error" in response:
            raise RuntimeError(f"A2A error {response['error']['code']}: {response['error']['message']}")
        return response["result"]["task"]

    def _http(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json", "A2A-Version": A2A_VERSION})
        if self.show_wire:
            print(f"\n──► {method} {url}" + (f"\n{json.dumps(body, indent=2, ensure_ascii=False)}" if body else ""))
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        if self.show_wire:
            print(f"◄── {json.dumps(result, indent=2, ensure_ascii=False)}")
        return result


def text_of(task: dict) -> str:
    """What the remote agent said: the question (INPUT_REQUIRED) or the result artifact (COMPLETED)."""
    if task["status"]["state"] == "TASK_STATE_INPUT_REQUIRED":
        return " ".join(p["text"] for p in task["status"]["message"]["parts"])
    return " ".join(p["text"] for a in task.get("artifacts", []) for p in a["parts"] if "text" in p)


if __name__ == "__main__":
    client = A2AClient("http://localhost:8001", show_wire=True)
    print(f"\nDiscovered: {client.card['name']} — skills: {[s['id'] for s in client.card['skills']]}")
    task = client.send("preciso de acesso ao SAP", user_email="joao@company.com")
    print(f"\n[{task['status']['state']}] {text_of(task)}")
    if task["status"]["state"] == "TASK_STATE_INPUT_REQUIRED":  # the remote agent asked; WE ask the user
        task = client.send("é para lançar as notas fiscais do mês", user_email="joao@company.com",
                           task_id=task["id"], context_id=task["contextId"])
        print(f"\n[{task['status']['state']}] {text_of(task)}")
