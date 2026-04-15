import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, validate_password, verify_password
from app.models.user import PasswordResetToken, User


router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    name: str | None = Field(default=None, max_length=120)
    remember_me: bool = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    remember_me: bool = True


class UserDTO(BaseModel):
    id: str
    email: EmailStr
    name: str
    avatar: str | None = None
    createdAt: datetime


class AuthResponse(BaseModel):
    user: UserDTO
    token: str
    token_expires_in_minutes: int


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=12)
    new_password: str = Field(..., min_length=6, max_length=128)


def _to_user_dto(user: User) -> UserDTO:
    return UserDTO(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar=user.avatar_url,
        createdAt=user.created_at,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.execute(select(User).where(User.email == request.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="该邮箱已注册")

    try:
        password_hash = hash_password(request.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    display_name = request.name.strip() if request.name and request.name.strip() else request.email.split("@")[0]

    user = User(
        email=request.email,
        password_hash=password_hash,
        name=display_name,
    )
    db.add(user)
    db.flush()

    db.commit()
    db.refresh(user)

    token_expire_minutes = (
        settings.ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER_ME
        if request.remember_me
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    token = create_access_token(user.id, expires_minutes=token_expire_minutes)
    return AuthResponse(user=_to_user_dto(user), token=token, token_expires_in_minutes=token_expire_minutes)


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == request.email)).scalar_one_or_none()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")

    user.last_login_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    token_expire_minutes = (
        settings.ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER_ME
        if request.remember_me
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    token = create_access_token(user.id, expires_minutes=token_expire_minutes)
    return AuthResponse(user=_to_user_dto(user), token=token, token_expires_in_minutes=token_expire_minutes)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="未登录")

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="无效令牌")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="无效令牌") from exc

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


@router.get("/me", response_model=UserDTO)
def me(current_user: User = Depends(get_current_user)):
    return _to_user_dto(current_user)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == request.email)).scalar_one_or_none()

    if not user:
        return ForgotPasswordResponse(message="如果该邮箱已注册，重置邮件将很快发送。")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db.add(reset)
    db.commit()

    return ForgotPasswordResponse(
        message="如果该邮箱已注册，重置邮件将很快发送。",
        reset_token=raw_token if settings.DEBUG else None,
    )


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        validate_password(request.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token_hash = hashlib.sha256(request.token.encode("utf-8")).hexdigest()

    reset_record = db.execute(
        select(PasswordResetToken).where(
            and_(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > datetime.utcnow(),
            )
        )
    ).scalar_one_or_none()

    if not reset_record:
        raise HTTPException(status_code=400, detail="重置链接无效或已过期")

    user = db.get(User, reset_record.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")

    user.password_hash = hash_password(request.new_password)
    reset_record.used_at = datetime.utcnow()

    db.add(user)
    db.add(reset_record)
    db.commit()

    return {"message": "密码已更新，请使用新密码登录"}
