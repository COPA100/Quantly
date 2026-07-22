from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserRead
from api.security.tokens import create_access_token
from api.services.auth import (
    EmailTakenError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenReuseError,
    authenticate_user,
    issue_refresh_token,
    register_user,
    revoke_all_devices,
    revoke_refresh_token,
    rotate_refresh_token,
)
from common.db import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserRead)
def register(payload: RegisterRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        user = register_user(db, payload.email, payload.password)
    except EmailTakenError as exc:
        raise HTTPException(status_code=409, detail="email already registered") from exc
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        user = authenticate_user(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail="invalid email or password") from exc
    access = create_access_token(user.id)
    refresh = issue_refresh_token(db, user.id)
    db.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        user, new_refresh = rotate_refresh_token(db, payload.refresh_token)
    except TokenReuseError as exc:
        db.commit()  # persist the family-wide revocation before rejecting
        raise HTTPException(status_code=401, detail="refresh token reuse detected") from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="invalid refresh token") from exc
    access = create_access_token(user.id)
    db.commit()
    return TokenPair(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=204)
def logout(payload: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    revoke_refresh_token(db, payload.refresh_token)
    db.commit()


@router.post("/logout-all", status_code=204)
def logout_all(payload: RefreshRequest, db: Annotated[Session, Depends(get_db)]):
    try:
        revoke_all_devices(db, payload.refresh_token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="invalid refresh token") from exc
    db.commit()
