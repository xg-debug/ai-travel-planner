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

    def to_storage_dict(self, *, plan_id: Optional[str] = None, created_at: Optional[str] = None) -> Dict[str, Any]:
        data = self.model_dump()
        if plan_id:
            data["id"] = plan_id
        if created_at:
            data["createdAt"] = created_at
        return data


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
                select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id)
            ).scalar_one_or_none()

        data = payload.to_storage_dict(
            plan_id=existing.id if existing else (payload.id or None),
            created_at=(existing.created_at.isoformat() if existing else None),
        )

        if existing:
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
            select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id)
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="行程不存在")

        data = payload.to_storage_dict(
            plan_id=plan_id,
            created_at=(row.payload().get("createdAt") or row.created_at.isoformat()),
        )
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
