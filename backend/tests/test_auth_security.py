from datetime import UTC, datetime, timedelta

import jwt
import pytest

from api.security.passwords import hash_password, verify_password
from api.security.tokens import (
    TokenError,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from common.config import get_settings


def test_hash_is_not_the_plain_password():
    hashed = hash_password("hunter2pw")
    assert hashed != "hunter2pw"
    assert hashed.startswith("$argon2")


def test_verify_password_matches_and_rejects():
    hashed = hash_password("hunter2pw")
    assert verify_password("hunter2pw", hashed) is True
    assert verify_password("wrongpass", hashed) is False


def test_same_password_hashes_differently():
    # per-hash salt means two hashes of the same password never match
    assert hash_password("samepw12") != hash_password("samepw12")


def test_access_token_round_trips_the_subject():
    claims = decode_access_token(create_access_token(7))
    assert claims["sub"] == "7"
    assert claims["type"] == "access"


def test_garbage_token_rejected():
    with pytest.raises(TokenError):
        decode_access_token("not.a.jwt")


def test_expired_token_rejected():
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": "1", "type": "access", "exp": int(past.timestamp())},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_token_signed_with_other_secret_rejected():
    future = datetime.now(UTC) + timedelta(minutes=5)
    token = jwt.encode(
        {"sub": "1", "type": "access", "exp": int(future.timestamp())},
        "some-other-secret",
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_non_access_token_rejected():
    settings = get_settings()
    future = datetime.now(UTC) + timedelta(minutes=5)
    token = jwt.encode(
        {"sub": "1", "type": "refresh", "exp": int(future.timestamp())},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenError):
        decode_access_token(token)


def test_refresh_token_hashing():
    raw = generate_refresh_token()
    digest = hash_refresh_token(raw)
    assert len(digest) == 64  # sha256 hex
    assert digest != raw
    assert hash_refresh_token(raw) == digest  # deterministic
    assert hash_refresh_token(generate_refresh_token()) != digest
