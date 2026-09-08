from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


STEP_PROGRESS: Dict[str, int] = {
    "request_analysis": 5,
    "weather_lookup": 16,
    "attraction_search": 28,
    "food_search": 40,
    "hotel_search": 52,
    "transport_planning": 64,
    "itinerary_review": 72,
    "itinerary_synthesis": 78,
    "budget_estimation": 90,
    "risk_notices": 95,
    "summary": 98,
}


@dataclass(frozen=True)
class PlanningEvent:
    """Stable event contract shared by API, jobs and client progress UIs."""

    run_id: str
    sequence: int
    step: str
    message: str
    progress: int
    detail: Dict[str, Any] = field(default_factory=dict)
    emitted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def as_payload(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "sequence": self.sequence,
            "step": self.step,
            "message": self.message,
            "progress": self.progress,
            "detail": dict(self.detail),
            "emitted_at": self.emitted_at,
        }


def progress_for_step(step: str) -> int:
    return STEP_PROGRESS.get(step, 0)
