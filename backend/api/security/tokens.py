import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from common.config import get_settings


class TokenError(Exception):
    """raised when an access token is missing, malformed, or expired."""


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError("invalid or expired token") from exc
    if claims.get("type") != "access":
        raise TokenError("wrong token type")
    return claims


def generate_refresh_token() -> str:
    # opaque random string, never a jwt, so it carries no readable claims
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw: str) -> str:
    # only the hash is stored, a db leak cannot reveal usable tokens
    return hashlib.sha256(raw.encode()).hexdigest()
