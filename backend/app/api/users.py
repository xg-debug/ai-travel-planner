import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User, UserPreference


router = APIRouter()


class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str
    avatar_url: Optional[str] = None
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


class UserPreferences(BaseModel):
    theme: str = "light"
    language: str = "zh-CN"
    currency: str = "CNY"
    notifications: dict = {
        "email": True,
        "push": True,
        "tripUpdates": True,
        "recommendations": True,
    }
    travel_style: dict = {
        "pace": "moderate",
        "accommodation": "mid-range",
        "food": "mixed",
        "transportation": "mixed",
    }


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        email_verified=user.email_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return _to_user_response(current_user)


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
    return _to_user_response(current_user)


@router.get("/me/preferences", response_model=UserPreferences)
def get_my_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = db.get(UserPreference, current_user.id)
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)
        db.commit()
        db.refresh(pref)

    return UserPreferences(
        theme=pref.theme,
        language=pref.language,
        currency=pref.currency,
        notifications=json.loads(pref.notifications_json),
        travel_style=json.loads(pref.travel_style_json),
    )


@router.put("/me/preferences", response_model=UserPreferences)
def update_my_preferences(
    preferences: UserPreferences,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = db.get(UserPreference, current_user.id)
    if not pref:
        pref = UserPreference(user_id=current_user.id)

    pref.theme = preferences.theme
    pref.language = preferences.language
    pref.currency = preferences.currency
    pref.notifications_json = json.dumps(preferences.notifications, ensure_ascii=False)
    pref.travel_style_json = json.dumps(preferences.travel_style, ensure_ascii=False)

    db.add(pref)
    db.commit()
    db.refresh(pref)

    return preferences
