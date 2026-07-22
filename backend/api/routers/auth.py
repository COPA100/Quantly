from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas.auth import RegisterRequest, UserRead
from api.services.auth import EmailTakenError, register_user
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
