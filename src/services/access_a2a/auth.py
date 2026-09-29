"""Who is calling, and on whose behalf — verified BEFORE any request reaches the protocol (lesson 2.5).

A Starlette AuthenticationBackend runs on every HTTP request, before the SDK's JSON-RPC handler:
- the Agent Card stays public (discovery needs no credentials — it has no secrets);
- /a2a requires a bearer token SIGNED by a caller we trust, addressed to US, not expired, for a known user.
Anything else → HTTP 401, and our business code never runs. The SDK then takes the verified user from
request.user (its default context builder) and scopes the task store by it.

This replaces lesson 2.2's naive identity (a header anyone could write). Now forging a user means forging a
signature — which needs the Service Desk's private key, which never leaves the Service Desk.
"""

import os
from pathlib import Path

import jwt
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
)
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse, Response

from src import data  # the company directory (shared infra): which users exist

_DEFAULT_KEYS = Path(__file__).resolve().parents[3] / ".keys"
# The IAM team's registry of callers it trusts: issuer → where its PUBLIC key is. Adding a client service is a
# deliberate act on OUR side (an entry here), not something a caller can claim.
TRUSTED_CALLERS = {
    "service-desk": Path(
        os.getenv("SERVICE_DESK_PUBLIC_KEY", _DEFAULT_KEYS / "service-desk.pub")
    ),
}
REQUIRED_CLAIMS = ["iss", "sub", "aud", "iat", "exp"]


class DelegatedTokenBackend(AuthenticationBackend):
    def __init__(self, audience: str, protected_path: str):
        self.audience = (
            audience  # our own RPC URL: a token for any other service is not for us
        )
        self.protected_path = protected_path

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, SimpleUser] | None:
        if conn.url.path != self.protected_path:
            return None  # public route (the Agent Card)
        scheme, _, token = conn.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthenticationError("Missing bearer token")
        try:
            # The issuer is read UNVERIFIED only to pick which public key to check with; the signature check
            # below (with issuer=...) is what makes the claim trustworthy.
            issuer = jwt.decode(token, options={"verify_signature": False}).get(
                "iss", ""
            )
            claims = jwt.decode(
                token,
                _public_key(issuer),
                algorithms=[
                    "EdDSA"
                ],  # pinned: never let the token choose (e.g. "none")
                audience=self.audience,
                issuer=issuer,
                options={"require": REQUIRED_CLAIMS},
            )
        except jwt.PyJWTError as e:
            raise AuthenticationError(f"Invalid token: {e}") from None
        if claims["sub"] not in data.USERS:
            raise AuthenticationError("Unknown user")
        return AuthCredentials(["delegated"]), SimpleUser(claims["sub"])


def _public_key(issuer: str) -> bytes:
    path = TRUSTED_CALLERS.get(issuer)
    if path is None:
        raise jwt.InvalidIssuerError(f"untrusted caller {issuer!r}")
    if not path.exists():
        raise jwt.InvalidKeyError(f"no public key for {issuer!r} yet")
    return (
        path.read_bytes()
    )  # read per call: a rotated key is picked up at once (tiny file)


def unauthorized(_conn: HTTPConnection, exc: AuthenticationError) -> Response:
    # 401 (not Starlette's default 400): "who are you?" failed. The WWW-Authenticate header says how to fix it.
    return JSONResponse(
        {"error": str(exc)}, status_code=401, headers={"WWW-Authenticate": "Bearer"}
    )
