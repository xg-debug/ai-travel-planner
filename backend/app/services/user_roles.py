from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin import UserRole
from app.models.user import User


ROLE_USER = "user"
ROLE_ADMIN = "admin"
ROLE_SUPER_ADMIN = "super_admin"
ADMIN_ROLES = {ROLE_ADMIN, ROLE_SUPER_ADMIN}
VALID_ASSIGNABLE_ROLES = {ROLE_USER, ROLE_ADMIN}


def normalize_role(role: str | None) -> str:
    value = (role or ROLE_USER).strip().lower()
    if value in {ROLE_USER, ROLE_ADMIN, ROLE_SUPER_ADMIN}:
        return value
    return ROLE_USER


def get_first_user_id(db: Session) -> str | None:
    return db.execute(select(User.id).order_by(User.created_at.asc(), User.id.asc()).limit(1)).scalar_one_or_none()


def get_user_role(db: Session, user: User) -> str:
    row = db.get(UserRole, user.id)
    if row:
        return normalize_role(row.role)
    if user.id == get_first_user_id(db):
        return ROLE_SUPER_ADMIN
    return ROLE_USER


def ensure_user_role(db: Session, user: User, role: str, assigned_by: str | None = None) -> UserRole:
    normalized = normalize_role(role)
    row = db.get(UserRole, user.id)
    if row:
        row.role = normalized
        row.assigned_by = assigned_by
        db.add(row)
        return row
    row = UserRole(user_id=user.id, role=normalized, assigned_by=assigned_by)
    db.add(row)
    return row
