"""The service catalog's own data. `approval`: "pre_approved" (delivered right away), "manager" (needs the
manager's approval + justification) or "blocked" (security policy — nobody can order it)."""

CATALOG = {
    "SW001": {"name": "7-Zip", "type": "software", "approval": "pre_approved", "description": "File archiver."},
    "SW002": {"name": "Zoom", "type": "software", "approval": "pre_approved", "description": "Video calls with customers."},
    "SW003": {"name": "Notepad++", "type": "software", "approval": "pre_approved", "description": "Text editor."},
    "SW004": {"name": "Adobe Acrobat Pro", "type": "software", "approval": "manager",
              "description": "Edit and sign PDFs. Paid license (US$ 20/month)."},
    "SW005": {"name": "Power BI Pro", "type": "software", "approval": "manager",
              "description": "Build and share BI reports. Paid license (US$ 14/month)."},
    "SW006": {"name": "Visual Studio Professional", "type": "software", "approval": "manager",
              "description": "IDE for software development. Paid license (US$ 45/month)."},
    "SW007": {"name": "AnyDesk", "type": "software", "approval": "blocked",
              "description": "Remote desktop tool.",
              "blocked_reason": "Remote-access tools are blocked by the security policy; IT support uses its own tool."},
    "SW008": {"name": "uTorrent", "type": "software", "approval": "blocked",
              "description": "P2P file sharing.", "blocked_reason": "P2P software is blocked by the security policy."},
    "HW001": {"name": "USB headset", "type": "equipment", "approval": "pre_approved", "description": "Headset for calls."},
    "HW002": {"name": "Wireless mouse and keyboard", "type": "equipment", "approval": "pre_approved",
              "description": "Mouse + keyboard kit."},
    "HW003": {"name": "27-inch external monitor", "type": "equipment", "approval": "manager",
              "description": "Second screen for the desk."},
    "HW004": {"name": "Laptop replacement", "type": "equipment", "approval": "manager",
              "description": "New laptop. Only for laptops 4+ years old, or out of warranty with a hardware failure."},
}

CATALOG_REQUESTS: dict[str, dict] = {}


def reset() -> None:
    """Back to the seed (tests, each eval run). Nobody outside the server can call it — on purpose."""
    CATALOG_REQUESTS.clear()
