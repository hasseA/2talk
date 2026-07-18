"""Opaque token utility tests."""

from app.auth.tokens import (
    generate_invitation_token,
    generate_session_token,
    hash_token,
    verify_token,
)


def test_hash_is_deterministic_without_containing_raw_token() -> None:
    token = generate_invitation_token()
    secret = "invitation-test-secret"

    first_hash = hash_token(token, secret)
    second_hash = hash_token(token, secret)

    assert first_hash == second_hash
    assert token not in first_hash
    assert verify_token(token, first_hash, secret)
    assert not verify_token("wrong-token", first_hash, secret)


def test_invitation_and_session_tokens_are_random() -> None:
    invitation_tokens = {generate_invitation_token() for _ in range(10)}
    session_tokens = {generate_session_token() for _ in range(10)}

    assert len(invitation_tokens) == 10
    assert len(session_tokens) == 10
    assert invitation_tokens.isdisjoint(session_tokens)


def test_empty_token_or_secret_is_rejected() -> None:
    for token, secret in (("", "secret"), ("token", "")):
        try:
            hash_token(token, secret)
        except ValueError:
            pass
        else:
            raise AssertionError("empty token inputs must be rejected")
