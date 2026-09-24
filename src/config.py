"""Model configuration: one model per ROLE, not one model for everything.

This is the "specialization" reason for splitting work (lesson 1.1): a cheap, fast model for
simple jobs (classification/routing) and a stronger one for the agent that reasons and uses tools.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    name: str
    # None = don't send the parameter (non-reasoning models like gpt-4o-mini reject it).
    # "none" = reasoning model with reasoning turned off. For gpt-6-luna, Chat Completions only
    # supports tool calling with reasoning "none"; turning it on requires the Responses API.
    reasoning_effort: str | None = None


# Classifier/router: used from lesson 1.3 on (triage).
CLASSIFIER = ModelConfig(name=os.getenv("CLASSIFIER_MODEL", "gpt-4o-mini"))

# Agent: conversation + tools.
AGENT = ModelConfig(
    name=os.getenv("AGENT_MODEL", "gpt-6-luna"),
    reasoning_effort=os.getenv("AGENT_REASONING_EFFORT", "none"),
)

# Price per 1M tokens (input, output), in US$. Reasoning tokens are billed as output.
PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-6-luna": (0.10, 0.50),
}
