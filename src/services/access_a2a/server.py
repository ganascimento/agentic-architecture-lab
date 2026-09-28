"""The Access agent as an independent A2A service — hand-written with the stdlib (lesson 2.2).

Imagine this runs on the IAM team's infrastructure. From the outside it's OPAQUE: callers see the Agent Card
and the messages; the prompt, the model and the tools stay inside. Inside, it's the same Access agent as
module 1 (same role, same tools) — only the way you reach it changed: HTTP + JSON-RPC 2.0 instead of a call.

What travels on the wire (A2A v1.0, JSON-RPC binding):
    GET  /.well-known/agent-card.json                → the Agent Card (who am I, skills, where to call)
    POST /a2a  {"method": "SendMessage", ...}        → {"result": {"task": {...}}}

No SDK on purpose: this is the naive version, to see what the SDK hides (lesson 2.3 migrates to it).
Run:  python -m src.services.access_a2a        (port 8001)
"""

import json
import threading
import uuid
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.auth import Session, session_for
from src.core.agent import Agent, Usage, total_usage
from src.services.a2a_protocol import A2A_VERSION, COMPLETED, INPUT_REQUIRED
from src.services.access_a2a.agent import ASK_USER, access_agent_for

PORT = 8001

def agent_card(port: int) -> dict:
    """The contract. The client calls whatever URL is here — a wrong URL means nobody can reach the agent."""
    return {
        "name": "Access Request Agent",
        "description": "Registers access requests to folders and systems (pending manager approval) and reports "
                       "their status. Never grants access.",
        "version": "1.0.0",
        "supportedInterfaces": [{"url": f"http://localhost:{port}/a2a", "protocolBinding": "JSONRPC",
                                 "protocolVersion": A2A_VERSION}],
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {"id": "access-request", "name": "Register an access request",
             "description": "Registers a request for access to a folder or system, with the user's justification.",
             "tags": ["access", "permission", "iam"],
             "examples": ["I need access to the Finance folder for the monthly closing"]},
            {"id": "access-status", "name": "Access request status",
             "description": "Lists the user's access requests and their approval status.",
             "tags": ["access", "status"], "examples": ["Was my SAP access request approved?"]},
        ],
    }

# JSON-RPC 2.0 error codes (-32601/-32602/-32700 are standard; -32001 is A2A's TaskNotFound).
PARSE_ERROR, METHOD_NOT_FOUND, INVALID_PARAMS, TASK_NOT_FOUND = -32700, -32601, -32602, -32001


class AccessA2AService:
    """The protocol logic, separate from HTTP so it can be tested without a server or an LLM."""

    def __init__(self, make_agent: Callable[[Session], Agent] = access_agent_for):
        self.make_agent = make_agent
        self.agents: dict[str, Agent] = {}  # contextId → the agent holding that conversation (its state)
        self.tasks: dict[str, dict] = {}

    def handle(self, request: dict) -> dict:
        if request.get("method") != "SendMessage":
            return _error(request, METHOD_NOT_FOUND, f"Method not found: {request.get('method')}")
        params = request.get("params") or {}
        message = params.get("message") or {}
        text = " ".join(p["text"] for p in message.get("parts", []) if "text" in p)
        if not text:
            return _error(request, INVALID_PARAMS, "The message needs at least one text part.")

        # ⚠️ INSECURE ON PURPOSE (lesson 2.2): the caller SAYS who the user is, and we believe it.
        # Anyone who can POST here can act as anyone — Finding 1.2 again, now between services.
        # Lesson 2.5 replaces this with a token signed by the identity side (token exchange).
        email = (params.get("metadata") or {}).get("userEmail", "")
        try:
            session = session_for(email)
        except KeyError:
            return _error(request, INVALID_PARAMS, f"Unknown user: {email!r}")

        # Continue an interrupted task (INPUT_REQUIRED) or start a new one.
        task_id = message.get("taskId")
        if task_id and task_id not in self.tasks:
            return _error(request, TASK_NOT_FOUND, f"Task not found: {task_id}")
        task = self.tasks.get(task_id or "") or {"id": str(uuid.uuid4()),
                                           "contextId": message.get("contextId") or str(uuid.uuid4())}
        agent = self.agents.get(task["contextId"])
        if agent is None:
            agent = self.agents[task["contextId"]] = self.make_agent(session)
        elif agent.session.email != session.email:
            # IDOR on the protocol: knowing a contextId/taskId is not permission to continue someone's task.
            # Same answer as "doesn't exist", so the error doesn't reveal that it does.
            return _error(request, TASK_NOT_FOUND, f"Task not found: {task_id or task['contextId']}")

        before = len(agent.tool_calls)
        reply = agent.reply(text)
        calls = agent.tool_calls[before:]
        question = next((c.arguments.get("question", "") for c in calls if c.name == ASK_USER), None)

        # The STATE is the code's decision, from an EXPLICIT signal: the agent called ask_user → INPUT_REQUIRED.
        # Anything else → COMPLETED, with or without work done. Default to COMPLETED because it fails SAFE:
        # if the LLM forgets ask_user and just writes a question, the task closes and the user's answer goes back
        # to the caller's hub (one extra hop) — instead of trapping the conversation here (the old default).
        if question is not None:
            task["status"] = {"state": INPUT_REQUIRED,
                              "message": {"messageId": str(uuid.uuid4()), "role": "ROLE_AGENT",
                                          "parts": [{"text": reply or question}]}}
        else:
            task["status"] = {"state": COMPLETED}
            # Text for the human, DATA for the machine (the caller doesn't parse prose to know what happened).
            # It's the business result — the tool's internals stay inside (opaque agent).
            parts: list[dict] = [{"text": reply}]
            if result := _business_result([c for c in calls if not c.is_error]):
                parts.append({"data": result})
            task["artifacts"] = [{"artifactId": str(uuid.uuid4()), "name": "result", "parts": parts}]
        self.tasks[task["id"]] = task
        return {"jsonrpc": "2.0", "id": request.get("id"), "result": {"task": task}}


    # --- The IAM team's own bill (the eval adds it to ours to compare with module 1) ---
    @property
    def usage(self) -> Usage:
        return total_usage([a.usage for a in self.agents.values()])

    def cost(self) -> float:
        return sum(a.cost() for a in self.agents.values())


def _business_result(calls: list) -> dict:
    result: dict = {}
    for call in calls:
        if call.name == "create_access_request":
            result["accessRequest"] = json.loads(call.result)
        elif call.name == "list_my_access_requests":
            result["accessRequests"] = json.loads(call.result)
    return result


def _error(request: dict, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": code, "message": message}}


def make_handler(service: AccessA2AService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # discovery: anyone can read the card (it has no secrets)
            if self.path == "/.well-known/agent-card.json":
                self._send(200, agent_card(self.server.server_address[1]))
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/a2a":
                return self._send(404, {"error": "not found"})
            try:
                request = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            except json.JSONDecodeError:
                return self._send(200, _error({}, PARSE_ERROR, "Invalid JSON"))
            self._send(200, service.handle(request))  # JSON-RPC: errors travel in the body, with HTTP 200

        def _send(self, status: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("A2A-Version", A2A_VERSION)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def start(service: AccessA2AService, port: int = 0, background: bool = True) -> tuple[ThreadingHTTPServer, str]:
    """Serves the agent (port 0 = any free port). The eval and the tests run it in a background thread."""
    server = ThreadingHTTPServer(("localhost", port), make_handler(service))
    if background:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://localhost:{server.server_port}"


def serve(port: int = PORT) -> None:
    server, url = start(AccessA2AService(), port, background=False)
    print(f"Access A2A agent on {url}  (card: /.well-known/agent-card.json)")
    server.serve_forever()
