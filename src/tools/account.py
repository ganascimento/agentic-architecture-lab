"""The user's own account. No tool here takes an email: there is no way to ASK for someone else's data.
(Compare with the old get_user(email), which leaked any employee's data — eval case 16.)"""

from src import data
from src.auth import Session
from src.tools._schema import NO_ARGS, Tool, definition


def get_my_profile(session: Session) -> dict:
    return {"email": session.email, **data.USERS[session.email]}


def request_password_reset(session: Session) -> dict:
    # Sensitive action with NO arguments: the link always goes to the logged-in user's registered email.
    data.PASSWORD_RESETS.append(session.email)
    return {"sent_to": session.email, "expires_in_minutes": 30}


TOOLS = [
    Tool(definition(
        "get_my_profile", "Returns the logged-in user's name, department and manager.", NO_ARGS,
    ), get_my_profile),
    Tool(definition(
        "request_password_reset",
        "Sends a password reset link to the logged-in user's registered email. Only for the user's own account.",
        NO_ARGS,
    ), request_password_reset),
]
