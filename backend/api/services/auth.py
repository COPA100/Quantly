from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.security.passwords import hash_password
from api.security.tokens import generate_refresh_token, hash_refresh_token
from common.config import get_settings
from common.models import RefreshToken, User


class AuthError(Exception):
    """base for auth failures the router maps to a 4xx response."""


class EmailTakenError(AuthError):
    """the email is already registered."""


def register_user(db: Session, email: str, password: str) -> User:
    email = email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise EmailTakenError(email)
    user = User(email=email, hashed_password=hash_password(password), auth_provider="local")
    db.add(user)
    db.flush()
    return user


def issue_refresh_token(db: Session, user_id: int) -> str:
    # store the hash, hand the caller the raw token to give the client
    settings = get_settings()
    raw = generate_refresh_token()
    token = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(raw),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(token)
    db.flush()
    return raw
