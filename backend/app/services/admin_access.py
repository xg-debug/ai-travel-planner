from dataclasses import dataclass

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.user_roles import ADMIN_ROLES, ROLE_SUPER_ADMIN, get_user_role


@dataclass
class AdminPrincipal:
    user: User
    role: str


def require_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminPrincipal:
    role = get_user_role(db, current_user)
    if role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return AdminPrincipal(user=current_user, role=role)


def require_super_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdminPrincipal:
    role = get_user_role(db, current_user)
    if role != ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="需要超级管理员权限")
    return AdminPrincipal(user=current_user, role=role)
