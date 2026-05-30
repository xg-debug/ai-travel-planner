from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.user_roles import get_user_role


router = APIRouter()


class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str
    avatar_url: Optional[str] = None
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


def _to_user_response(user: User, db: Session) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=get_user_role(db, user),
        avatar_url=user.avatar_url,
        email_verified=user.email_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _to_user_response(current_user, db)


@router.put("/me", response_model=UserResponse)
def update_me(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_update.name is not None:
        current_user.name = user_update.name.strip()
    if user_update.avatar_url is not None:
        current_user.avatar_url = user_update.avatar_url.strip() or None

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _to_user_response(current_user, db)
