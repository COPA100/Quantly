from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from api.security.tokens import generate_refresh_token, hash_refresh_token
from common.config import get_settings
from common.models import RefreshToken


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
