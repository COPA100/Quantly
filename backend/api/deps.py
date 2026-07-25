from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.security.google import verify_google_id_token
from api.security.tokens import TokenError, decode_access_token
from common.db import get_db
from common.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_google_verifier():
    # indirection so tests can swap in a fake verifier without calling google
    return verify_google_id_token


def get_enqueuer() -> Callable[[int], str]:
    # indirection so tests can enqueue without a live broker. imported lazily so
    # the module loads even where only the api half is installed.
    from worker.celery_app import celery_app

    def enqueue(portfolio_id: int) -> str:
        result = celery_app.send_task("analyze_portfolio", args=[portfolio_id])
        return result.id

    return enqueue


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise unauthorized from exc
    user = db.get(User, int(claims["sub"]))
    if user is None:
        raise unauthorized
    return user
