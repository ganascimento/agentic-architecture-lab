"""What both sides of A2A share: the protocol, not code. In real life this is the A2A spec (and the official SDK,
lesson 2.3) — the Service Desk and the IAM team each implement it, and agree on nothing else."""

A2A_VERSION = "1.0"

COMPLETED, INPUT_REQUIRED, FAILED = "TASK_STATE_COMPLETED", "TASK_STATE_INPUT_REQUIRED", "TASK_STATE_FAILED"
FINISHED = {COMPLETED, FAILED, "TASK_STATE_CANCELED", "TASK_STATE_REJECTED"}


def text_of(task: dict) -> str:
    """What the remote agent said: the question (INPUT_REQUIRED) or the result artifact (COMPLETED)."""
    if task["status"]["state"] == INPUT_REQUIRED:
        return " ".join(p["text"] for p in task["status"]["message"]["parts"])
    return " ".join(p["text"] for a in task.get("artifacts", []) for p in a["parts"] if "text" in p)


def data_of(task: dict) -> dict:
    """The structured part of the artifacts — for machines (the caller doesn't parse prose to know what happened)."""
    return {k: v for a in task.get("artifacts", []) for p in a["parts"] if "data" in p for k, v in p["data"].items()}
