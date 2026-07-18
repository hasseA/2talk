"""Secure opaque-token generation and keyed hashing helpers."""

import hashlib
import hmac
import secrets

TOKEN_BYTES = 32


def generate_invitation_token() -> str:
    """Generate a cryptographically secure invitation token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def generate_session_token() -> str:
    """Generate a cryptographically secure participant-session token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str, secret: str) -> str:
    """Create a deterministic HMAC-SHA-256 token digest for storage."""
    if not token:
        raise ValueError("token must not be empty")
    if not secret:
        raise ValueError("secret must not be empty")
    return hmac.new(
        secret.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_token(token: str, expected_hash: str, secret: str) -> bool:
    """Compare a token with a stored digest using constant-time comparison."""
    if not token or not expected_hash or not secret:
        return False
    candidate_hash = hash_token(token, secret)
    return hmac.compare_digest(candidate_hash, expected_hash)
