import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.trip_plan import TripPlan
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_version(expected: int | None, actual: int) -> None:
    if expected != actual:
        raise HTTPException(status_code=409, detail="行程已在其他设备更新，请刷新后重试")


def _activity_cost(activity: Dict[str, Any], travelers: int) -> float:
    try:
        explicit = float(activity.get("cost") or 0)
        ticket = float(activity.get("ticketPrice") or 0)
        return max(0, explicit if explicit > 0 else ticket * travelers)
    except (TypeError, ValueError):
        return 0


def _category(activity: Dict[str, Any]) -> str:
    kind = str(activity.get("type") or "")
    return {"food": "餐饮", "transport": "交通", "shopping": "购物"}.get(kind, "门票")


def _reconcile_day_budget(data: Dict[str, Any], old_day: Dict[str, Any], new_day: Dict[str, Any]) -> None:
    travelers = max(1, int(data.get("travelers") or 1))
    delta: Dict[str, float] = {}
    for sign, day in ((-1, old_day), (1, new_day)):
        for activity in day.get("activities") or []:
            name = _category(activity)
            delta[name] = delta.get(name, 0) + sign * _activity_cost(activity, travelers)
    budget = dict(data.get("budget") or {})
    categories = []
    for item in budget.get("categories") or []:
        category = dict(item)
        amount_delta = delta.pop(str(category.get("name") or ""), 0)
        category["amount"] = max(0, round(float(category.get("amount") or 0) + amount_delta, 2))
        categories.append(category)
    for name, amount_delta in delta.items():
        if amount_delta > 0:
            categories.append({"name": name, "amount": round(amount_delta, 2), "planned": 0})
    if categories:
        budget["categories"] = categories
        budget["total"] = round(sum(float(item.get("amount") or 0) for item in categories), 2)
        data["budget"] = budget
    new_day["totalCost"] = round(sum(_activity_cost(a, travelers) for a in new_day.get("activities") or []), 2)


class TripPlanPayload(BaseModel):
    id: Optional[str] = None
    departureCity: Optional[str] = None
    destination: str
    startDate: str
    endDate: str
    travelers: int
    interests: List[str] = Field(default_factory=list)
    budget: Dict[str, Any] = Field(default_factory=dict)
    days: List[Dict[str, Any]] = Field(default_factory=list)
    weather: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    hotels: List[Dict[str, Any]] = Field(default_factory=list)
    intercityTransport: Dict[str, Any] = Field(default_factory=dict)
    plan: str = ""
    planningWarnings: List[str] = Field(default_factory=list)
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    version: Optional[int] = None

    def to_storage_dict(self, *, plan_id: Optional[str] = None, created_at: Optional[str] = None) -> Dict[str, Any]:
        data = self.model_dump()
        if plan_id:
            data["id"] = plan_id
        if created_at:
            data["createdAt"] = created_at
        return data


class TripDayPatch(BaseModel):
    version: int = Field(ge=1)
    day: Dict[str, Any]


@router.get("/plans")
def list_trip_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            select(TripPlan).where(TripPlan.user_id == current_user.id).order_by(TripPlan.updated_at.desc())
        )
        .scalars()
        .all()
    )
    return [row.payload() for row in rows]


@router.get("/plans/{plan_id}")
def get_trip_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="行程不存在")
    return row.payload()


@router.post("/plans")
def create_trip_plan(
    payload: TripPlanPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        plan_id = payload.id or ""
        existing = None
        if plan_id:
            existing = db.execute(
                select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id).with_for_update()
            ).scalar_one_or_none()

        data = payload.to_storage_dict(
            plan_id=existing.id if existing else (payload.id or None),
            created_at=(existing.created_at.isoformat() if existing else None),
        )

        if existing:
            _require_version(payload.version, existing.version)
            existing.version += 1
            existing.sync_from_payload(data)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing.payload()

        # SQLAlchemy's UUID default is assigned on INSERT. Persist the id in the
        # JSON payload up front as well, otherwise list/history returns id=null
        # even though direct lookup by the database row id succeeds.
        new_plan_id = payload.id or str(uuid.uuid4())
        data["id"] = new_plan_id
        data["createdAt"] = data.get("createdAt") or datetime.utcnow().isoformat()
        row = TripPlan(
            id=new_plan_id,
            user_id=current_user.id,
            destination=payload.destination,
            start_date=payload.startDate,
            end_date=payload.endDate,
        )
        row.sync_from_payload(data)
        db.add(row)
        db.commit()
        db.refresh(row)
        result = row.payload()
        if not result.get("id"):
            result["id"] = row.id
        return result
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Error saving trip plan: %s", exc)
        raise HTTPException(status_code=500, detail="保存行程失败，请稍后重试")


@router.put("/plans/{plan_id}")
def update_trip_plan(
    plan_id: str,
    payload: TripPlanPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id).with_for_update()
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="行程不存在")
        _require_version(payload.version, row.version)

        data = payload.to_storage_dict(
            plan_id=plan_id,
            created_at=(row.payload().get("createdAt") or row.created_at.isoformat()),
        )
        row.version += 1
        row.sync_from_payload(data)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.payload()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Error updating trip plan: %s", exc)
        raise HTTPException(status_code=500, detail="更新行程失败，请稍后重试")


@router.patch("/plans/{plan_id}/days/{day_index}")
def update_trip_day(
    plan_id: str,
    day_index: int,
    patch: TripDayPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if day_index < 0:
        raise HTTPException(status_code=422, detail="无效的行程日期")
    try:
        row = db.execute(
            select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id).with_for_update()
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="行程不存在")
        _require_version(patch.version, row.version)
        data = row.payload()
        days = list(data.get("days") or [])
        if day_index >= len(days):
            raise HTTPException(status_code=422, detail="无效的行程日期")
        old_day = days[day_index]
        new_day = dict(patch.day)
        new_day["date"] = old_day.get("date")
        new_day.pop("map_route", None)
        new_day["routeNeedsRefresh"] = True
        _reconcile_day_budget(data, old_day, new_day)
        days[day_index] = new_day
        data["days"] = days
        data["updatedAt"] = datetime.utcnow().isoformat()
        row.version += 1
        row.sync_from_payload(data)
        db.commit()
        db.refresh(row)
        return row.payload()
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Error updating trip day: %s", exc)
        raise HTTPException(status_code=500, detail="更新行程失败，请稍后重试") from exc


@router.delete("/plans/{plan_id}")
def delete_trip_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="行程不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}
