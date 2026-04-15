from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError

from app.core.config import settings

# 处理用户认证相关的安全功能：密码加密、密码验证、JWT令牌生成

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def validate_password(password: str) -> None:
    if len(password) < 6:
        raise ValueError("密码长度至少为 6 位")
    if len(password) > 128:
        raise ValueError("密码长度不能超过 128 位字符")


def hash_password(password: str) -> str:
    validate_password(password)
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except UnknownHashError:
        return False


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
