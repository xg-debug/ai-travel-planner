from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping

from app.core.config import settings
from app.services.travel_intent import normalize_trip_city_and_query

TripPlanningState = Dict[str, Any]

WORKFLOW_STEP_PROGRESS: Dict[str, int] = {
    "request_analysis": 5,
    "weather_lookup": 12,
    "attraction_search": 22,
    "food_search": 32,
    "hotel_search": 42,
    "transport_planning": 60,
    "itinerary_review": 68,
    "itinerary_synthesis": 70,
    "budget_estimation": 94,
    "risk_notices": 96,
    "summary": 98,
}

def trip_request_to_state(request: Any) -> TripPlanningState:
    payload = _model_dump(request)
    destination = _required_text(payload, "destination")
    days = int(payload.get("days") or 1)
    query = str(payload.get("additionalRequirements") or "").strip()
    if not query:
        query = f"{destination} {days}日游"
    normalized = normalize_trip_city_and_query(destination, query)
    budget_amount = _safe_float(payload.get("budgetAmount"))

    return {
        "query": normalized["query"],
        "city": normalized["city"],
        "departure_city": _first_text(payload, "departureCity"),
        "days": days,
        "preferences": _preferences(payload),
        "accommodation_preference": str(payload.get("accommodationPreference") or "mid-range"),
        "budget": _budget_level(budget_amount, days, int(payload.get("travelers") or 1)),
        "budget_amount": budget_amount,
        "travelers": int(payload.get("travelers") or 1),
        "start_date": _required_text(payload, "startDate"),
        "outbound_departure_datetime": _date_time_text(payload, "startDate", "departureTime"),
        "return_arrival_datetime": _date_time_text(payload, "endDate", "returnArrivalTime"),
    }


def validate_trip_state(state: TripPlanningState) -> None:
    city = str(state.get("city", "") or "").strip()
    if not city:
        raise ValueError("目的地城市不能为空")
    if len(city) > 50 or not all(ord(c) > 32 for c in city):
        raise ValueError("目的地城市名称不合法")
    if not state.get("query"):
        raise ValueError("旅行需求不能为空")
    days = int(state.get("days") or 0)
    if days <= 0:
        raise ValueError("旅行天数必须大于0")
    if days > settings.MAX_TRIP_DAYS:
        raise ValueError(f"旅行天数不能超过{settings.MAX_TRIP_DAYS}天")
    travelers = int(state.get("travelers") or 1)
    if travelers < 1 or travelers > 20:
        raise ValueError("出行人数必须在1-20人之间")
    budget_amount = int(state.get("budget_amount") or 0)
    if budget_amount < 0:
        raise ValueError("预算金额不能为负数")
    if budget_amount > 0:
        per_person_per_day = budget_amount / travelers / days
        if per_person_per_day < 100:
            raise ValueError(f"人均每日预算过低（¥{per_person_per_day:.0f}），建议至少¥100/人/天")
    outbound_departure = parse_request_datetime(state.get("outbound_departure_datetime"))
    return_arrival = parse_request_datetime(state.get("return_arrival_datetime"))
    if outbound_departure and return_arrival and return_arrival <= outbound_departure:
        raise ValueError("返程到达时间必须晚于去程出发时间")
    departure_city = str(state.get("departure_city", "") or "").strip()
    if departure_city and len(departure_city) > 50:
        raise ValueError("出发城市名称过长")


def parse_request_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError("出发和返程时间格式必须为 YYYY-MM-DD HH:MM")


def _model_dump(request: Any) -> Dict[str, Any]:
    if hasattr(request, "model_dump"):
        return request.model_dump()
    if isinstance(request, Mapping):
        return dict(request)
    return dict(getattr(request, "__dict__", {}) or {})


def _first_text(payload: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key}不能为空")
    return value


def _preferences(payload: Mapping[str, Any]) -> List[str]:
    interests = payload.get("interests")
    if isinstance(interests, list):
        return [str(item).strip() for item in interests if str(item).strip()]
    return []


def _budget_level(amount: float, days: int, travelers: int) -> str:
    per_person_per_day = amount / max(days, 1) / max(travelers, 1)
    if per_person_per_day < 400:
        return "经济"
    if per_person_per_day < 1000:
        return "中等"
    return "豪华"


def _date_time_text(payload: Mapping[str, Any], date_key: str, time_key: str) -> str:
    date_value = _required_text(payload, date_key)
    time_value = _first_text(payload, time_key) or "00:00"
    return f"{date_value} {time_value}" if date_value and time_value else ""


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0
