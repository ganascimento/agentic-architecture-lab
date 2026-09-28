"""Model configuration. One model per ROLE is possible (lesson 1.1: specialization) — module 1 had a
gpt-4o-mini classifier for routing (see the module-1 branch), which turned out MORE expensive per token
than gpt-6-luna. Today every agent runs on AGENT.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    name: str
    # None = don't send the parameter (non-reasoning models reject it).
    # "none" = reasoning model with reasoning turned off. For gpt-6-luna, Chat Completions only
    # supports tool calling with reasoning "none"; turning it on requires the Responses API.
    reasoning_effort: str | None = None


# Agent: conversation + tools.
AGENT = ModelConfig(
    name=os.getenv("AGENT_MODEL", "gpt-6-luna"),
    reasoning_effort=os.getenv("AGENT_REASONING_EFFORT", "none"),
)

# Price per 1M tokens (input, output), in US$. Reasoning tokens are billed as output.
PRICES = {
    "gpt-6-luna": (0.10, 0.50),
}

# Where the IAM team's Access agent lives (module 2). Only the base URL: the rest comes from its Agent Card.
ACCESS_AGENT_URL = os.getenv("ACCESS_AGENT_URL", "http://localhost:8001")
