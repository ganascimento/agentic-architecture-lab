<div align="center">

# 🧪 agentic-architecture-lab

Hands-on lab for agentic system architecture: multi-agent design, A2A, MCP, LangGraph, governance, RAG and evals, built step by step through an AI-powered IT Service Desk.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-gpt--6--luna_%2B_gpt--4o--mini-412991?style=flat&logo=openai&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-0A9EDC?style=flat&logo=pytest&logoColor=white)

</div>

---

## ✨ Features

- 🧠 **Framework-free agent loop**: the model calls tools in a plain Python loop you can read end to end.
- 📚 **Knowledge base lookup**: the agent follows official procedures before guiding the user.
- 🎫 **Ticket escalation**: unresolved issues become L2 tickets with a structured summary.
- 🔐 **Access requests with human approval**: the agent can only *register* a request; it has no tool that grants access.
- 💰 **Cost and call tracking**: every turn shows model calls and estimated cost, so architectures can be compared with numbers.

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| LLM | OpenAI (`openai` SDK): `gpt-6-luna` for the agent (tools), `gpt-4o-mini` for classification |
| Config | `python-dotenv` |
| Tests | `pytest` |

## 🗺 Roadmap

Each module adds one concept to the same system.

| # | Module | Status |
|---|---|---|
| 1 | Multi-Agent Architecture: single-agent baseline → supervisor + specialists | 🚧 in progress |
| 2 | A2A (Agent2Agent protocol) | ⏳ |
| 3 | MCP (Model Context Protocol) | ⏳ |
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

# Create and activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate      # Windows (PowerShell): .venv\Scripts\Activate.ps1

pip install -r requirements.txt

cp .env.example .env   # then put your OpenAI API key in .env
```

### Environment Variables

| Variable | Description | Required |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key | ✅ |
| `AGENT_MODEL` | Model for the agent that uses tools (default `gpt-6-luna`) | ⚪ optional |
| `AGENT_REASONING_EFFORT` | Reasoning effort for the agent model (default `none`) | ⚪ optional |
| `CLASSIFIER_MODEL` | Model for classification/routing (default `gpt-4o-mini`) | ⚪ optional |

### Commands

Every time you open a new terminal, activate the virtual environment first:

```bash
source .venv/bin/activate      # the prompt now starts with (.venv)
```

Then, with the venv active:

| Command | What it does |
|---|---|
| `python -m src` | Starts the Service Desk chat |
| `python -m pytest -q` | Runs the tests (no LLM calls, no cost) |
| `python -m evals.run` | Runs the agent eval (calls the LLM, ~US$ 0.01) |
| `pip install -r requirements.txt` | Installs/updates dependencies |
| `deactivate` | Leaves the virtual environment |

### Running the chat

```bash
python -m src
```

Chat commands: `/new` starts a new conversation, `/state` shows created tickets and access requests, `/quit` exits.

Try these messages:

```
my vpn won't connect
I'm ana@company.com and I need access to the Finance folder
I'm joao@company.com, the VPN has been down since yesterday and I need access to SAP
```

## 🧪 Testing

The tools are deterministic, so their tests don't call the LLM:

```bash
python -m pytest -q
```

## 📊 Evals

The agent's behavior is measured with a mini-eval: 18 cases (knowledge base, tickets, access requests, two problems in one message, prompt injection, out of scope), each run 3 times and graded by code, based on which tools were called and what was replied.

```bash
python -m evals.run                   # all cases, 3 runs each
python -m evals.run --runs 1 --case 10 11
```

Results are saved to `evals/results/` so architectures can be compared on pass rate, cost and latency.

## 📁 Project Structure

```
src/
├── agent.py      # The agent: system prompt + the tool-use loop
├── config.py     # One model per role (classifier vs agent) + prices
├── tools.py      # Tool definitions (what the LLM sees) and implementations (what the code runs)
├── data.py       # Fake company systems: users, knowledge base, tickets
└── __main__.py   # Terminal chat
tests/            # Tool tests (no LLM calls)
evals/            # Agent eval: cases, runner and saved results
notes/            # Architecture notes and decisions (PT-BR)
```
