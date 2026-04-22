import json
import uuid
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TripPlan(Base):
    __tablename__ = "trip_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    destination: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    start_date: Mapped[str] = mapped_column(String(20), nullable=False)
    end_date: Mapped[str] = mapped_column(String(20), nullable=False)
    travelers: Mapped[int] = mapped_column(nullable=False, default=1)
    interests_json: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    budget_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    budget_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned", index=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def payload(self) -> Dict[str, Any]:
        try:
            return json.loads(self.payload_json)
        except Exception:
            return {}

    def sync_from_payload(self, payload: Dict[str, Any]) -> None:
        budget = payload.get("budget") or {}
        interests = payload.get("interests") or []
        days = payload.get("days") or []

        self.destination = payload.get("destination", self.destination)
        self.start_date = payload.get("startDate", self.start_date)
        self.end_date = payload.get("endDate", self.end_date)
        self.travelers = int(payload.get("travelers") or 1)
        self.interests_json = list(interests)
        self.budget_total = float(budget.get("total") or 0)
        self.budget_currency = budget.get("currency") or "CNY"
        self.status = payload.get("status") or ("planned" if days else "draft")
        self.cover_image_url = self._extract_cover_image(payload)
        self.payload_json = json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _extract_cover_image(payload: Dict[str, Any]) -> str | None:
        recommendations = payload.get("recommendations") or []
        for item in recommendations:
            image_url = item.get("image") or item.get("image_url")
            normalized = TripPlan._normalize_cover_image(image_url)
            if normalized:
                return normalized

        for day in payload.get("days") or []:
            for activity in day.get("activities") or []:
                image_url = activity.get("image") or activity.get("image_url")
                normalized = TripPlan._normalize_cover_image(image_url)
                if normalized:
                    return normalized
        return None

    @staticmethod
    def _normalize_cover_image(image_url: Any) -> str | None:
        text = str(image_url or "").strip()
        if not text:
            return None
        if text.startswith("data:image/"):
            return None
        if len(text) > 500:
            return None
        if text.startswith(("http://", "https://")):
            return text
        return None
