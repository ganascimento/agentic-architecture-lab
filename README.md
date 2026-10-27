<div align="center">

# 🧪 agentic-architecture-lab

Hands-on lab for agentic system architecture: multi-agent design, A2A, MCP, LangGraph, governance, RAG and evals, built step by step through an AI-powered IT Service Desk.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-gpt--6--luna-412991?style=flat&logo=openai&logoColor=white)
![A2A](https://img.shields.io/badge/A2A-v1.0-34A853?style=flat)
![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=flat&logo=pytest&logoColor=white)

</div>

---

## ✨ Features

- 🧠 **Framework-free agent loop**: the model calls tools in a plain Python loop you can read end to end.
- 🔀 **Handoff hub-and-spoke**: a reception agent routes the conversation to specialists (Support, Account, Catalog), who talk to the user directly.
- 🌐 **Agent2Agent (A2A)**: the Access agent is another team's independent service, discovered through its Agent Card and called over JSON-RPC with streaming progress (official `a2a-sdk`).
- 🔌 **Model Context Protocol (MCP)**: every company system (tickets, knowledge base, account, assets, catalog) is its own MCP server over HTTP that owns its data. The Service Desk discovers their tools at runtime and the agents call them like local ones (official `mcp` SDK, spec `2026-07-28`, stateless; older `2025-11-25` clients still work).
- 🔐 **Login + least privilege**: identity comes from the session (never from the chat), tools only touch the user's own data, and nothing in the Service Desk can grant access. Between services, a short-lived signed token (JWT) says who calls and on whose behalf.
- 🧾 **Provenance checks**: the code verifies that a justification (access, licensed software) or a ticket resolution came from the user's own words.
- 🏢 **A realistic IT domain**: knowledge base with internal-only articles, incidents and maintenance windows, tickets with deadlines (SLA), escalation and duplicate detection, remote device diagnostics, and a service catalog (pre-approved, manager-approved and blocked items). Business rules live in code, not in prompts.
- 💰 **Evals with numbers**: pass rate, model calls, cost and latency per case.

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| LLM | OpenAI (`openai` SDK, Chat Completions): `gpt-6-luna` |
| Agent-to-agent | A2A v1.0 on the official SDK (`a2a-sdk` 1.1.5, pinned), JSON-RPC + streaming (SSE), served by uvicorn |
| Tools | MCP `2026-07-28` on the official SDK (`mcp` 2.2.0, pinned), Streamable HTTP |
| Service identity | Signed JWT (`pyjwt`, Ed25519): who calls and on whose behalf |
| Config | `python-dotenv` |
| Tests | `pytest` |

## 🗺 Roadmap

Each module adds one concept to the same system. `main` is the current system; every finished module is
kept in its own branch (`module-N`) and tag (`module-N-final`).

| # | Module | Status |
|---|---|---|
| 1 | Multi-Agent Architecture: single agent, routing, handoff (mesh and hub) | ✅ done — branch `module-1` |
| 2 | A2A (Agent2Agent protocol): remote agent, official SDK, streaming, signed service identity | ✅ done — branch `module-2` |
| 3 | MCP (Model Context Protocol): hand-written stdio server, then every system as an MCP server over Streamable HTTP (SDK) | ✅ done — branch `module-3` |
| 4 | Advanced LangGraph: checkpoints, human-in-the-loop | ⏳ |
| 5 | Agent Builder + Registry | ⏳ |
| 6 | Security & Governance | ⏳ |
| 7 | Advanced RAG | ⏳ |
| 8 | Observability & Evals | ⏳ |

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- An [OpenAI API key](https://platform.openai.com/api-keys)

### Installation

```bash
git clone <repo-url>
cd agentic-architecture-lab

python3 -m venv .venv
source .venv/bin/activate      # Windows (PowerShell): .venv\Scripts\Activate.ps1

pip install -r requirements.txt

cp .env.example .env   # then put your OpenAI API key in .env
```

### Environment Variables

| Variable | Description | Required |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key | ✅ |
| `AGENT_MODEL` | Model for every agent (default `gpt-6-luna`) | ⚪ optional |
| `AGENT_REASONING_EFFORT` | Reasoning effort (default `none`; the Chat Completions API only does tool calling with `none` for this model) | ⚪ optional |
| `ACCESS_AGENT_URL` | Base URL of the Access agent (default `http://localhost:8001`); the rest comes from its Agent Card | ⚪ optional |

### Commands

Every new terminal needs the virtual environment active first: `source .venv/bin/activate`.

| Command | What it does |
|---|---|
| `python -m src.services.access_a2a` | Starts the **Access agent** (the IAM team's A2A service) on port 8001 |
| `python -m src.services.mcp_servers` | Starts the company's **systems** (5 MCP servers over HTTP) on port 8002, one path each |
| `python -m src` | Starts the **Service Desk** chat (needs the Access agent and the MCP servers running) |
| `python -m src.services.a2a_client` | A2A demo: discovers the Access agent and runs a two-step task, showing streaming progress |
| `python -m src.services.mcp_client` | MCP demo: talks to the tickets server and shows discovery, what the LLM sees and tools/call |
| `python -m pytest -q` | Runs the tests (no LLM calls, no cost) |
| `python -m evals.run` | Runs the eval (starts the Access agent and the MCP servers by itself; calls the LLM) |

### Running the Service Desk

The Service Desk, the Access agent and the company's systems are separate processes, so use **three terminals**:

```bash
# terminal 1 — the IAM team's Access agent (A2A)
python -m src.services.access_a2a

# terminal 2 — the company's systems: tickets, knowledge, account, assets, catalog (MCP over HTTP)
python -m src.services.mcp_servers

# terminal 3 — the Service Desk
python -m src
```

Log in with a test account (plaintext passwords, study only):

| Username | Password | User |
|---|---|---|
| `ana` | `ana123` | Ana Souza (Sales) |
| `joao` | `joao123` | João Lima (Finance) |
| `carlos` | `carlos123` | Carlos Reis (Sales manager) |
| `marta` | `marta123` | Marta Alves (Finance manager) |
| `pedro` | `pedro123` | Pedro Costa (Sales, **contractor**: pre-approved catalog items only) |
| `bruno` | `bruno123` | Bruno Tavares (IT: sees internal KB articles) |

Chat commands: `/new` starts a new conversation, `/quit` exits.
All the data lives in other processes (the IAM service and the MCP servers): ask the agent about it ("my tickets", "my access requests").

Try these messages:

```
my vpn won't connect
I need access to the Finance folder for the monthly closing
the VPN has been down since yesterday and I need access to SAP to post invoices
I forgot my password
my laptop is really slow                        ← remote diagnostic of the user's laptop
is anything down today?                         ← every active incident
INC0001 is past its deadline, please escalate it
I need 7-Zip / I need Power BI Pro to build the closing reports
```

### Seeing A2A in action

With the Access agent running, the demo client shows discovery and a two-step task (`INPUT_REQUIRED` → `COMPLETED`):

```bash
python -m src.services.a2a_client
```

```
Discovered: Access Request Agent — skills: ['access-request', 'access-status']
  … Checking your request...                       ← streaming: WORKING arrives before the answer
[TASK_STATE_INPUT_REQUIRED] What is the justification for SAP access?
  … Checking your request...
[TASK_STATE_COMPLETED] Access request REQ0002 registered, pending your manager's approval.
```

Under the hood: `GET /.well-known/agent-card.json` (discovery) → `POST /a2a` `SendStreamingMessage` with an
`Authorization: Bearer <signed JWT>` header → `GetTask` for the final task. A call without a valid token gets
HTTP 401 before it reaches the agent.

### Seeing MCP in action

```bash
python -m src.services.mcp_client
```

With the MCP servers running, it prints the negotiated version, one tool translated into the function-calling format the LLM gets, and `tools/call` for ana. Asking about another user's ticket returns `isError: true` (a refusal the LLM can read).

Under the hood each request is one `POST /<system>/mcp`: a JSON-RPC body (version, client capabilities and the user in `params._meta`) plus headers that mirror it (`MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`), so a gateway can route by tool without parsing JSON. A call with no user in `_meta` gets a JSON-RPC error (a problem in the calling code).

> ⚠️ Known gap (planned for module 6): the servers trust the user email in `_meta`, so anything that reaches the port can act as anyone. They listen on `127.0.0.1` only. The fix is the same signed token used for A2A.

## 🧪 Testing

No test calls the LLM. The tools are deterministic. The A2A tests serve a fake Access agent over real HTTP, including forged, expired and wrong-audience tokens. The MCP tests start the real MCP servers over HTTP, check the raw wire, and run an older (`2025-11-25`) client against them.

```bash
python -m pytest -q
```

## 📊 Evals

50 cases (knowledge base, tickets, SLA and escalation, duplicates, device diagnostics, service catalog, access requests, several requests in one message, multi-turn dialogs, direct and indirect prompt injection, impersonation, IDOR, internal data, out of scope), graded by code. The eval starts the Access agent and the MCP servers in background threads, and adds the Access agent's LLM cost to ours.

```bash
python -m evals.run                    # all cases, 3 runs each
python -m evals.run --runs 1 --case 10 31
```

Results are saved to `evals/results/` (git-ignored: regenerated on every run). Latest full run (50 cases × 3): **98%**, 4.7 model calls and 6.6 s per case.

## 📁 Project Structure

```
src/
├── __main__.py            # Terminal chat: login + Service Desk
├── config.py · auth.py    # Model/prices · local login → Session
├── identity.py            # Signed delegated token (JWT, Ed25519) for calls to other services
├── data.py                # Shared infra: company clock, login accounts, user directory
├── core/agent.py          # The generic agent loop
├── tools/                 # Host tool machinery: run_tool (permissions, provenance), merge of registries
├── architectures/         # The hub: triage + specialists (Support, Account, Catalog), and the remote (A2A) node
└── services/
    ├── a2a_client.py      # A2A client on the SDK (discovery + streaming send + GetTask)
    ├── access_a2a/        # The IAM team's Access agent as an A2A service (server, auth, agent, tools, data)
    ├── mcp_client.py      # MCP client on the SDK (HTTP): discover, list, call, translate to function calling
    └── mcp_servers/       # The company's systems as MCP servers: server.py (protocol) + one package per system
                           # (tickets, knowledge, account, assets, catalog), each with its tools and its data
tests/                     # No-LLM tests
evals/                     # Eval cases, runner and saved results
notes/SUMMARY.md           # Study notes and architecture decisions (PT-BR)
```
