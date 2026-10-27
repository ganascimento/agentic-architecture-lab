"""The knowledge base's own data (articles) and the status page's (incidents, maintenance). Read-only: no reset.

KB `visibility`: "public" (any employee) or "internal" (IT staff only — filtered by CODE, in tools.py).
"""

KB_ARTICLES = [
    {
        "id": "KB001", "title": "VPN won't connect", "category": "network", "visibility": "public",
        "updated": "2026-06-10",
        "tags": ["vpn", "network", "forticlient", "connection", "remote"],
        "content": (
            "1. Check that your password hasn't expired (the VPN uses your network password). "
            "2. If you changed your password recently, wait 15 minutes for it to sync. "
            "3. Close and reopen FortiClient; if it persists, reinstall it from the Software Portal. "
            "4. If you see 'error -14', open a ticket for the Network team."
        ),
    },
    {
        "id": "KB002", "title": "Forgot password / password expired", "category": "account", "visibility": "public",
        "updated": "2026-02-01",
        "tags": ["password", "reset", "forgot", "login", "expired"],
        "content": (
            "The Service Desk can send a password reset link to the user's registered email. "
            "If the account is locked, open a ticket."
        ),
    },
    {
        "id": "KB003", "title": "Printer printing blurry or failing", "category": "hardware", "visibility": "public",
        "updated": "2025-11-20",
        "tags": ["printer", "printing", "blurry", "toner"],
        "content": (
            "Run the printhead cleaning from the printer panel. If it continues, open a ticket for Hardware. "
            "(IT staff: panel maintenance procedures are in KB017.)"
        ),
    },
    {
        "id": "KB004", "title": "Outlook not syncing emails", "category": "email", "visibility": "public",
        "updated": "2026-03-15",
        "tags": ["outlook", "email", "e-mail", "sync"],
        "content": "Close Outlook and run 'outlook.exe /resetnavpane'. If that fails, recreate the profile in Control Panel.",
    },
    {
        "id": "KB005", "title": "Access to network folders and systems", "category": "access", "visibility": "public",
        "updated": "2026-01-05",
        "tags": ["access", "folder", "permission", "system", "grant"],
        "content": (
            "Access requires a formal request with a justification and approval from the direct manager. "
            "The Service Desk registers the request; access is only granted after approval."
        ),
    },
    {
        "id": "KB006", "title": "Slow laptop", "category": "hardware", "visibility": "public",
        "updated": "2026-05-02",
        "tags": ["slow", "slowness", "laptop", "freezing", "performance"],
        "content": (
            "Restart the device (many people only suspend it). Check for pending updates. "
            "The Service Desk can run a remote diagnostic on the device. If it persists, open a ticket."
        ),
    },
    {
        "id": "KB007", "title": "SAP slow or unavailable", "category": "software", "visibility": "public",
        "updated": "2026-04-18",
        "tags": ["sap", "slow", "unavailable", "erp", "timeout"],
        "content": (
            "First check the system status: if there is an ongoing incident, do NOT open a new ticket — "
            "inform the user and the incident number. Otherwise, clear the SAP GUI cache and try again."
        ),
    },
    {
        "id": "KB008", "title": "Office Wi-Fi (CORP-WIFI) not connecting", "category": "network",
        "visibility": "public", "updated": "2026-07-22",
        "tags": ["wifi", "wi-fi", "wireless", "corp-wifi", "office"],
        "content": (
            "CORP-WIFI only works inside the office and uses your network password. Forget the network and "
            "reconnect. Guests use CORP-GUEST. Working from home? That's the VPN, see KB001."
        ),
    },
    {
        "id": "KB009", "title": "Teams: no audio, camera or screen sharing", "category": "software",
        "visibility": "public", "updated": "2026-08-30",
        "tags": ["teams", "audio", "microphone", "camera", "meeting", "call"],
        "content": (
            "In Teams, open Settings > Devices and pick the right microphone and camera. Close other apps that "
            "use the camera. For screen sharing on macOS, allow Teams in System Settings > Privacy."
        ),
    },
    {
        "id": "KB010", "title": "Requesting software or equipment", "category": "catalog", "visibility": "public",
        "updated": "2026-09-01",
        "tags": ["software", "install", "license", "equipment", "catalog", "monitor", "headset"],
        "content": (
            "Everything comes from the Service Catalog. Pre-approved items (free tools, headset, mouse) are "
            "delivered or installed right away. Licensed software and bigger equipment need the manager's "
            "approval, with a justification. Some software is blocked by the security policy (remote-access "
            "and P2P tools). Contractors can only order pre-approved items."
        ),
    },
    {
        "id": "KB011", "title": "MFA: new phone or lost authenticator", "category": "account", "visibility": "public",
        "updated": "2026-06-30",
        "tags": ["mfa", "authenticator", "2fa", "phone", "token"],
        "content": (
            "If you still have the old phone, move your accounts inside the authenticator app. If you lost it, "
            "open a ticket (category access): the MFA reset requires identity verification by a phone call."
        ),
    },
    {
        "id": "KB012", "title": "Laptop replacement policy", "category": "catalog", "visibility": "public",
        "updated": "2026-09-01",
        "tags": ["laptop", "replacement", "old", "warranty", "new", "upgrade"],
        "content": (
            "A laptop can be replaced when it is 4 years old or more, or when it is out of warranty with a "
            "hardware failure. Request 'Laptop replacement' from the Service Catalog; the manager approves."
        ),
    },
    {
        "id": "KB013", "title": "Disk full / low disk space", "category": "hardware", "visibility": "public",
        "updated": "2026-04-02",
        "tags": ["disk", "storage", "space", "full"],
        "content": (
            "Empty the Downloads folder and the recycle bin. In OneDrive, use 'Free up space' on old folders "
            "(files stay in the cloud). Above 90% the laptop gets slow."
        ),
    },
    {
        "id": "KB014", "title": "SharePoint / OneDrive not syncing", "category": "software", "visibility": "public",
        "updated": "2026-05-19",
        "tags": ["sharepoint", "onedrive", "sync", "files"],
        "content": (
            "First check the system status: SharePoint incidents affect everyone, don't open a ticket for them. "
            "Otherwise, pause and resume sync in the OneDrive icon, then sign out and back in."
        ),
    },
    {
        "id": "KB015", "title": "Ticket deadlines (SLA) and escalation", "category": "tickets", "visibility": "public",
        "updated": "2026-01-10",
        "tags": ["sla", "deadline", "escalate", "escalation", "urgent", "priority"],
        "content": (
            "Response deadline by priority: high 4 hours, medium 24 hours, low 72 hours. A ticket can only be "
            "escalated after its deadline has passed. Before that, add a comment with new information."
        ),
    },
    {
        "id": "KB016", "title": "[Runbook] VPN error -14 on FortiGate", "category": "network",
        "visibility": "internal", "updated": "2026-06-10",
        "tags": ["vpn", "error", "-14", "fortigate", "tunnel", "runbook"],
        "content": (
            "Error -14 = stale tunnel for the user. On the FortiGate console: 'diagnose vpn tunnel flush <user>', "
            "then ask the user to reconnect. If it repeats, check the user's group in the VPN portal."
        ),
    },
    {
        "id": "KB017", "title": "[Internal] Printer panel maintenance", "category": "hardware",
        "visibility": "internal", "updated": "2025-11-20",
        "tags": ["printer", "panel", "admin", "maintenance", "pin"],
        "content": (
            "Printer fleet admin panel PIN: 7342. Deep clean: Menu > Service > Printhead > Deep clean (3 cycles). "
            "Never share the PIN with end users."
        ),
    },
]

# System status: incidents and scheduled maintenance. Opening one ticket per affected user would flood L2.
SYSTEM_STATUS = {
    "vpn": {"status": "operational"},
    "email": {
        "status": "operational",
        "maintenance": {"window": "2026-10-04 02:00-04:00", "note": "Mail server patching; email may be unavailable."},
    },
    "sap": {
        "status": "degraded", "incident": "MAJ-042", "note": "Slowness since 08:00, team working on it.",
        "updates": ["08:00 slowness reported by several users", "09:30 cause found (database lock), fix in progress"],
    },
    "teams": {"status": "operational"},
    "wifi": {"status": "operational"},
    "sharepoint": {
        "status": "outage", "incident": "MAJ-043",
        "note": "SharePoint Online unavailable for some users (provider-side incident).",
        "updates": ["09:10 provider confirmed the incident, no forecast yet"],
    },
}
