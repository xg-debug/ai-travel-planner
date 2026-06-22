from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.admin import UserActivityEvent
from app.models.trip_plan import TripPlan
from app.models.user import User
from app.services.admin_access import AdminPrincipal, require_admin, require_super_admin
from app.services.runtime_config import (
    LLM_PROVIDERS,
    MAP_PROVIDERS,
    build_runtime_config_snapshot,
    normalize_llm_model,
    set_setting_value,
)
from app.services.user_roles import (
    ROLE_SUPER_ADMIN,
    VALID_ASSIGNABLE_ROLES,
    ensure_user_role,
    get_user_role,
)


router = APIRouter()


class LLMSettingsUpdate(BaseModel):
    provider: str | None = None
    model: str | None = Field(default=None, max_length=120)
    api_key: str | None = Field(default=None, max_length=500)


class MapSettingsUpdate(BaseModel):
    provider: str | None = None
    api_key: str | None = Field(default=None, max_length=500)


class RuntimeSettingsUpdate(BaseModel):
    llm: LLMSettingsUpdate | None = None
    map: MapSettingsUpdate | None = None


class UserRoleUpdate(BaseModel):
    role: str


def _date_key(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return datetime.fromisoformat(str(value)).date().isoformat()
    except ValueError:
        return None


def _parse_date_param(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式必须为 YYYY-MM-DD") from exc


def _build_day_labels(days: int, start_date: str | None, end_date: str | None) -> list[str]:
    today = datetime.utcnow().date()
    parsed_start = _parse_date_param(start_date)
    parsed_end = _parse_date_param(end_date)

    if parsed_start and parsed_end:
        if parsed_start > parsed_end:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        if (parsed_end - parsed_start).days > 180:
            raise HTTPException(status_code=400, detail="自定义时间范围不能超过 180 天")
        return [
            (parsed_start + timedelta(days=offset)).isoformat()
            for offset in range((parsed_end - parsed_start).days + 1)
        ]

    safe_days = max(1, min(days, 180))
    return [(today - timedelta(days=offset)).isoformat() for offset in range(safe_days - 1, -1, -1)]


def _safe_interests(raw: Any) -> list[str]:
    value = raw
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = []
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _user_payload(db: Session, user: User, trip_count: int = 0) -> dict[str, Any]:
    role = get_user_role(db, user)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": role,
        "avatarUrl": user.avatar_url,
        "emailVerified": user.email_verified,
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
        "lastLoginAt": user.last_login_at,
        "tripCount": trip_count,
        "isSuperAdmin": role == ROLE_SUPER_ADMIN,
    }


@router.get("/me")
def admin_me(
    principal: AdminPrincipal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {
        **_user_payload(db, principal.user),
        "permissions": {
            "canViewDashboard": True,
            "canManageSettings": True,
            "canManageUsers": principal.role == ROLE_SUPER_ADMIN,
        },
    }


@router.get("/overview")
def overview(
    days: int = Query(default=14, ge=1, le=180),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    _principal: AdminPrincipal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.execute(select(User)).scalars().all()
    trips = db.execute(select(TripPlan)).scalars().all()
    events = db.execute(select(UserActivityEvent)).scalars().all()

    today = datetime.utcnow().date()
    day_labels = _build_day_labels(days, start_date, end_date)

    registrations_by_day = Counter(_date_key(user.created_at) for user in users)
    login_events = [event for event in events if event.event_type == "login"]
    logins_by_day = Counter(_date_key(event.created_at) for event in login_events)
    if not login_events:
        logins_by_day = Counter(_date_key(user.last_login_at) for user in users if user.last_login_at)
    generated_by_day = Counter(_date_key(trip.created_at) for trip in trips)
    active_users_by_day: dict[str, set[str]] = defaultdict(set)

    if login_events:
        for event in login_events:
            login_day = _date_key(event.created_at)
            if login_day:
                active_users_by_day[login_day].add(event.user_id)
    else:
        for user in users:
            login_day = _date_key(user.last_login_at)
            if login_day:
                active_users_by_day[login_day].add(user.id)

    trip_count_by_user: Counter[str] = Counter()
    destination_counts: Counter[str] = Counter()
    theme_counts: Counter[str] = Counter()
    for trip in trips:
        trip_count_by_user[trip.user_id] += 1
        created_day = _date_key(trip.created_at)
        updated_day = _date_key(trip.updated_at)
        if created_day:
            active_users_by_day[created_day].add(trip.user_id)
        if updated_day:
            active_users_by_day[updated_day].add(trip.user_id)
        if trip.destination:
            destination_counts[str(trip.destination).strip()] += 1
        for interest in _safe_interests(trip.interests_json):
            theme_counts[interest] += 1

    roles = [get_user_role(db, user) for user in users]
    series = [
        {
            "date": day,
            "registrations": registrations_by_day.get(day, 0),
            "logins": logins_by_day.get(day, 0),
            "activeUsers": len(active_users_by_day.get(day, set())),
            "tripGenerations": generated_by_day.get(day, 0),
        }
        for day in day_labels
    ]

    recent_trips = sorted(trips, key=lambda item: item.created_at, reverse=True)[:8]
    user_by_id = {user.id: user for user in users}
    user_trip_counts = sorted(
        [_user_payload(db, user, trip_count_by_user.get(user.id, 0)) for user in users],
        key=lambda item: (-int(item["tripCount"]), str(item["createdAt"])),
    )[:12]

    return {
        "totals": {
            "users": len(users),
            "admins": len([role for role in roles if role in {"admin", ROLE_SUPER_ADMIN}]),
            "superAdmins": len([role for role in roles if role == ROLE_SUPER_ADMIN]),
            "trips": len(trips),
            "registrationsToday": registrations_by_day.get(today.isoformat(), 0),
            "loginsToday": logins_by_day.get(today.isoformat(), 0),
            "activeToday": len(active_users_by_day.get(today.isoformat(), set())),
            "tripsToday": generated_by_day.get(today.isoformat(), 0),
        },
        "dailySeries": series,
        "topDestinations": [
            {"name": name, "count": count} for name, count in destination_counts.most_common(8) if name
        ],
        "topThemes": [{"name": name, "count": count} for name, count in theme_counts.most_common(8) if name],
        "userTripCounts": user_trip_counts,
        "recentTrips": [
            {
                "id": trip.id,
                "destination": trip.destination,
                "status": trip.status,
                "createdAt": trip.created_at,
                "updatedAt": trip.updated_at,
                "user": {
                    "id": trip.user_id,
                    "name": user_by_id.get(trip.user_id).name if user_by_id.get(trip.user_id) else "未知用户",
                    "email": user_by_id.get(trip.user_id).email if user_by_id.get(trip.user_id) else "",
                },
            }
            for trip in recent_trips
        ],
    }


@router.get("/runtime-status")
def runtime_status(
    _principal: AdminPrincipal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    snapshot = build_runtime_config_snapshot(db)
    selected_llm = next(
        item for item in snapshot["llm"]["providers"] if item["id"] == snapshot["llm"]["provider"]
    )
    selected_map = next(
        item for item in snapshot["map"]["providers"] if item["id"] == snapshot["map"]["provider"]
    )
    return {
        **snapshot,
        "health": {
            "llmConfigured": selected_llm["hasKey"],
            "mapConfigured": selected_map["hasKey"],
            "warnings": [
                message
                for message in [
                    None if selected_llm["hasKey"] else "当前大模型供应商尚未配置 API Key",
                    None if selected_map["hasKey"] else "当前地图供应商尚未配置 API Key",
                ]
                if message
            ],
        },
    }


@router.get("/settings")
def get_settings(
    _principal: AdminPrincipal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return build_runtime_config_snapshot(db)


@router.put("/settings")
def update_settings(
    payload: RuntimeSettingsUpdate,
    principal: AdminPrincipal = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if payload.llm:
        provider = (payload.llm.provider or "").strip().lower()
        if provider:
            if provider not in LLM_PROVIDERS:
                raise HTTPException(status_code=400, detail="不支持的大模型供应商")
            set_setting_value(db, "llm.provider", provider, principal.user.id)
        else:
            provider = str(build_runtime_config_snapshot(db)["llm"]["provider"])

        normalized_model = normalize_llm_model(provider, payload.llm.model)
        if normalized_model:
            set_setting_value(db, "llm.model", normalized_model, principal.user.id)

        if payload.llm.api_key is not None and payload.llm.api_key.strip():
            api_key_setting = LLM_PROVIDERS[provider]["api_key_setting"]
            set_setting_value(db, api_key_setting, payload.llm.api_key.strip(), principal.user.id)

    if payload.map:
        provider = (payload.map.provider or "").strip().lower()
        if provider:
            if provider not in MAP_PROVIDERS:
                raise HTTPException(status_code=400, detail="不支持的地图供应商")
            set_setting_value(db, "map.provider", provider, principal.user.id)
        else:
            provider = str(build_runtime_config_snapshot(db)["map"]["provider"])

        if payload.map.api_key is not None and payload.map.api_key.strip():
            api_key_setting = MAP_PROVIDERS[provider]["api_key_setting"]
            set_setting_value(db, api_key_setting, payload.map.api_key.strip(), principal.user.id)

    db.commit()
    return build_runtime_config_snapshot(db)


@router.get("/users")
def list_users(
    _principal: AdminPrincipal = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    users = db.execute(select(User).order_by(User.created_at.desc())).scalars().all()
    trip_counts = dict(
        db.execute(select(TripPlan.user_id, func.count(TripPlan.id)).group_by(TripPlan.user_id)).all()
    )
    return {"users": [_user_payload(db, user, int(trip_counts.get(user.id, 0))) for user in users]}


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    principal: AdminPrincipal = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == principal.user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的权限")

    current_role = get_user_role(db, target)
    if current_role == ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=400, detail="超级管理员角色不可降级")

    role = payload.role.strip().lower()
    if role not in VALID_ASSIGNABLE_ROLES:
        raise HTTPException(status_code=400, detail="只能设置为管理员或普通用户")

    ensure_user_role(db, target, role, principal.user.id)
    db.commit()
    db.refresh(target)
    trip_count = db.execute(select(func.count(TripPlan.id)).where(TripPlan.user_id == target.id)).scalar_one()
    return _user_payload(db, target, int(trip_count))
