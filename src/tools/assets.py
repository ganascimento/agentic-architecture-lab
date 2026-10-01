"""IT assets (CMDB): the user's own devices and a remote diagnostic.

Same ownership rule as tickets (IDOR): an asset id is not permission. The diagnostic's FINDINGS are computed
by code from the telemetry — the LLM explains them, it doesn't decide that "94% disk" is a problem.
The diagnostic is also the first slow, multi-step operation of the system: a natural case for MCP's progress
notifications (module 3). Here it answers at once.
"""

from datetime import datetime

from src import data
from src.auth import Session
from src.tools._schema import NO_ARGS, Tool, definition

REPLACEMENT_AGE_YEARS = 4  # KB012


def _date(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d")


def age_years(device: dict) -> float:
    return round((data.now() - _date(device["purchased"])).days / 365.25, 1)


def in_warranty(device: dict) -> bool:
    return data.now() <= _date(device["warranty_until"])


def replacement_eligible(device: dict) -> bool:
    """KB012, in code: 4+ years old (the 'out of warranty with a hardware failure' path needs a technician)."""
    return device["type"] == "laptop" and age_years(device) >= REPLACEMENT_AGE_YEARS


def _own_device(session: Session, asset_id: str) -> dict:
    device = data.DEVICES.get(asset_id.upper())
    if device is None or device["owner"] != session.email:
        raise ValueError(f"Device {asset_id} not found among your devices.")
    return device


def list_my_devices(session: Session) -> list[dict]:
    return [
        {"asset_id": aid, "type": d["type"], "model": d["model"], "purchased": d["purchased"],
         "in_warranty": in_warranty(d)}
        for aid, d in data.DEVICES.items() if d["owner"] == session.email
    ]


def run_device_diagnostics(session: Session, asset_id: str) -> dict:
    device = _own_device(session, asset_id)
    if device["type"] != "laptop":
        raise ValueError(f"Remote diagnostics are only available for laptops ({asset_id.upper()} is a {device['type']}).")
    t, age = device["telemetry"], age_years(device)
    findings = []
    if t["disk_used_pct"] >= 90:
        findings.append(f"Disk almost full ({t['disk_used_pct']}%): see KB013.")
    if t["uptime_days"] >= 7:
        findings.append(f"Not restarted for {t['uptime_days']} days (suspending is not restarting): see KB006.")
    if t["pending_updates"]:
        findings.append(f"{t['pending_updates']} pending updates.")
    if t["battery_health_pct"] < 60:
        findings.append(f"Battery health at {t['battery_health_pct']}%: the battery needs replacement.")
    if t["ram_gb"] <= 8:
        findings.append(f"Only {t['ram_gb']} GB of RAM, below the current standard (16 GB).")
    if replacement_eligible(device):
        findings.append(f"Device is {age} years old: eligible for replacement (KB012).")
    if not in_warranty(device):
        findings.append(f"Out of warranty since {device['warranty_until']}.")
    return {
        "asset_id": asset_id.upper(), "model": device["model"], "age_years": age, "in_warranty": in_warranty(device),
        "telemetry": t, "findings": findings or ["No problems found."],
    }


TOOLS = [
    Tool(definition(
        "list_my_devices", "Lists the devices (laptops, phones) assigned to the logged-in user.", NO_ARGS,
    ), list_my_devices),
    Tool(definition(
        "run_device_diagnostics",
        "Runs a remote diagnostic on one of the logged-in user's laptops (disk, restarts, updates, battery, age, "
        "warranty). Use it for device problems like slowness, battery or storage; get the asset id from "
        "list_my_devices.",
        {
            "type": "object",
            "properties": {"asset_id": {"type": "string", "description": "e.g. LAP-0142"}},
            "required": ["asset_id"],
        },
    ), run_device_diagnostics),
]
