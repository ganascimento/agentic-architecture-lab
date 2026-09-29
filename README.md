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
- 🔀 **Handoff hub-and-spoke**: a reception agent routes the conversation to specialists (Support, Account), who talk to the user directly.
- 🌐 **Agent2Agent (A2A)**: the Access agent is another team's independent service, discovered through its Agent Card and called over JSON-RPC with streaming progress (official `a2a-sdk`).
- 🔐 **Login + least privilege**: identity comes from the session (never from the chat), tools only touch the user's own data, and nothing in the Service Desk can grant access. Between services, a short-lived signed token (JWT) says who calls and on whose behalf.
- 🧾 **Provenance checks**: the code verifies that an access justification came from the user's own words.
- 💰 **Evals with numbers**: pass rate, model calls, cost and latency per case.

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| LLM | OpenAI (`openai` SDK, Chat Completions): `gpt-6-luna` |
| Agent-to-agent | A2A v1.0 on the official SDK (`a2a-sdk` 1.1.5, pinned), JSON-RPC + streaming (SSE), served by uvicorn |
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
| 3 | MCP (Model Context Protocol) | 🚧 next |
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
| `python -m src` | Starts the **Service Desk** chat (needs the Access agent running) |
| `python -m src.services.a2a_client` | A2A demo: discovers the Access agent and runs a two-step task, showing streaming progress |
| `python -m pytest -q` | Runs the tests (no LLM calls, no cost) |
| `python -m evals.run` | Runs the eval (starts the Access agent by itself; calls the LLM) |

### Running the Service Desk

The Service Desk and the Access agent are two separate processes, so use **two terminals**:

```bash
# terminal 1 — the IAM team's Access agent
python -m src.services.access_a2a

# terminal 2 — the Service Desk
python -m src
```

Log in with a test account (plaintext passwords, study only):

| Username | Password | User |
|---|---|---|
| `ana` | `ana123` | Ana Souza (Sales) |
| `joao` | `joao123` | João Lima (Finance) |
| `carlos` | `carlos123` | Carlos Reis (Sales manager) |
| `marta` | `marta123` | Marta Alves (Finance manager) |

Chat commands: `/new` starts a new conversation, `/state` shows tickets and password resets, `/quit` exits.
Access requests live in the Access agent's service: ask the agent about them ("my access requests").

Try these messages:

```
my vpn won't connect
I need access to the Finance folder for the monthly closing
the VPN has been down since yesterday and I need access to SAP to post invoices
I forgot my password
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

## 🧪 Testing

No test calls the LLM: the tools are deterministic, and the A2A tests serve a fake Access agent over real HTTP, including forged, expired and wrong-audience tokens.

```bash
python -m pytest -q
```

## 📊 Evals

35 cases (knowledge base, tickets, access requests, several requests in one message, multi-turn dialogs, prompt injection, impersonation, IDOR, out of scope), graded by code. The eval starts the Access agent in a background thread, and adds its LLM cost to ours.

```bash
python -m evals.run                    # all cases, 3 runs each
python -m evals.run --runs 1 --case 10 31
```

Results are saved to `evals/results/` (git-ignored: regenerated on every run). Latest full run (35 cases × 3): **93%**, 4.7 model calls and 6.1 s per case.

## 📁 Project Structure

```
src/
├── __main__.py            # Terminal chat: login + Service Desk
├── config.py · auth.py    # Model/prices · local login → Session
├── identity.py            # Signed delegated token (JWT, Ed25519) for calls to other services
├── data.py                # Fake company systems: accounts, directory, KB, tickets, system status
├── core/agent.py          # The generic agent loop
├── tools/                 # The Service Desk's tools (knowledge, tickets, account) + provenance check
├── architectures/         # The hub: triage + specialists, and the remote (A2A) node
└── services/
    ├── a2a_client.py      # A2A client on the SDK (discovery + streaming send + GetTask)
    └── access_a2a/        # The IAM team's Access agent as an A2A service (server, auth, agent, tools, data)
tests/                     # No-LLM tests
evals/                     # Eval cases, runner and saved results
notes/SUMMARY.md           # Study notes and architecture decisions (PT-BR)
```
