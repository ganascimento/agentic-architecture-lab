"""The Service Desk's identity toward OTHER services (lesson 2.5): a short-lived token, signed by us.

Two questions, one token (lesson 2.1's two layers):
- WHO IS CALLING?  → the signature. Only the Service Desk holds its private key; a valid signature proves the
  call came from it (iss = "service-desk"). The receiver checks it with our PUBLIC key — which can't sign.
- ON WHOSE BEHALF? → the claims: sub = the logged-in user (from OUR login session, never from the chat),
  aud = the ONE service this token is for (useless if replayed elsewhere), exp = seconds, not hours.

Why asymmetric (Ed25519) and not a shared secret (HMAC): with a shared secret, the IAM team could also MINT
tokens "from the Service Desk". With a key pair, verifying and signing are different powers.

⚠️ The trust boundary that remains: the IAM service believes whatever `sub` the Service Desk signs. If the Service
Desk is compromised, it can act as any user. The real fix is an identity provider (IdP) doing token exchange
(RFC 8693): the Service Desk trades the USER's own token for one scoped to IAM, so it can't invent users.
That needs real user authentication — the project's final phase.

Keys: generated on first use into .keys/ (git-ignored) — a dev shortcut. In production: a secret manager for the
private key, and the public key published at a URL the receivers fetch (JWKS), which also allows rotation.
"""

import time
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SERVICE_ID = "service-desk"  # the "iss" claim: how the receivers know which public key to check against
TOKEN_TTL = 60  # seconds: a token per call, so a leaked one is worthless almost at once
KEYS_DIR = Path(__file__).resolve().parents[1] / ".keys"
PRIVATE_KEY = KEYS_DIR / f"{SERVICE_ID}.pem"
PUBLIC_KEY = KEYS_DIR / f"{SERVICE_ID}.pub"  # what we hand to the teams that must trust us


def delegated_token(user_email: str, audience: str) -> str:
    """A token saying "the Service Desk calls <audience> on behalf of <user_email>", valid for TOKEN_TTL seconds."""
    now = int(time.time())
    claims = {"iss": SERVICE_ID, "sub": user_email, "aud": audience, "iat": now, "exp": now + TOKEN_TTL}
    return jwt.encode(claims, _private_key(), algorithm="EdDSA")


def _private_key() -> Ed25519PrivateKey:
    if not PRIVATE_KEY.exists():
        _create_key_pair()
    key = serialization.load_pem_private_key(PRIVATE_KEY.read_bytes(), password=None)
    assert isinstance(key, Ed25519PrivateKey)
    return key


def _create_key_pair() -> None:
    key = Ed25519PrivateKey.generate()
    KEYS_DIR.mkdir(exist_ok=True)
    PRIVATE_KEY.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                              serialization.NoEncryption()))
    PRIVATE_KEY.chmod(0o600)  # only this user reads the private key
    PUBLIC_KEY.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                         serialization.PublicFormat.SubjectPublicKeyInfo))
