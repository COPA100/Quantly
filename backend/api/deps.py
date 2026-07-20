from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from common.db import get_db
from common.models import User

# stand-in identity until real auth lands in phase 4
DEV_USER_EMAIL = "dev@quantly.local"


def get_current_user(db: Annotated[Session, Depends(get_db)]) -> User:
    # every portfolio belongs to this seeded user for now, phase 4 swaps in
    # the real jwt-authenticated user without changing the endpoint signatures
    user = db.scalar(select(User).where(User.email == DEV_USER_EMAIL))
    if user is None:
        user = User(email=DEV_USER_EMAIL)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
