from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Sequence

from app.core.config import settings
from app.trip_planning.candidates import (
    build_source_metadata,
    candidate_has_real_source,
    clean_poi_search_query,
    filter_real_candidates,
    safe_float,
    safe_int,
    score_general_candidate,
)
from app.trip_planning.utils import compact_name, dedupe


def extract_itinerary_data(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("itinerary", "plan", "days"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def normalize_itinerary(plan: Sequence[Dict[str, Any]], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    total_days = max(int(state.get("days", 1) or 1), 1)
    start = _parse_start_date(state.get("start_date"))

    for idx, day in enumerate(list(plan)[:total_days]):
        activities: List[Dict[str, Any]] = []
        for activity in (day.get("activities", []) or [])[: settings.MAX_ACTIVITIES_PER_DAY]:
            next_activity = dict(activity)
            next_activity.setdefault("time", "")
            next_activity.setdefault("title", "")
            next_activity.setdefault("description", "")
            next_activity.setdefault("type", "")
            next_activity.setdefault("location", next_activity.get("title", ""))
            next_activity["duration"] = max(safe_int(next_activity.get("duration"), 90), settings.MIN_ACTIVITY_DURATION)
            next_activity["cost_estimate"] = safe_int(next_activity.get("cost_estimate"), 0)
            next_activity["ticket_price"] = safe_int(next_activity.get("ticket_price"), 0)
            next_activity.setdefault("tips", "")
            next_activity.setdefault("transportation", "")
            activities.append(next_activity)

        normalized.append(
            {
                "day": idx + 1,
                "date": (start + timedelta(days=idx)).isoformat() if start else day.get("date"),
                "theme": str(day.get("theme", "")).strip(),
                "summary": str(day.get("summary", "")).strip(),
                "weather_advice": str(day.get("weather_advice", "") or day.get("weatherAdvice", "")).strip(),
                "budget": day.get("budget"),
                "hotel_recommendation": day.get("hotel_recommendation"),
                "activities": activities,
            }
        )

    while len(normalized) < total_days:
        idx = len(normalized)
        normalized.append(
            {
                "day": idx + 1,
                "date": (start + timedelta(days=idx)).isoformat() if start else None,
                "theme": "",
                "summary": "",
                "weather_advice": "",
                "budget": None,
                "hotel_recommendation": None,
                "activities": [],
            }
        )
    return normalized


def select_state_candidate_for_activity(
    state: Dict[str, Any],
    activity: Dict[str, Any],
    used_poi_names: Iterable[str],
) -> Dict[str, Any] | None:
    used = set(used_poi_names)
    source_id = str(activity.get("source_id", "") or "").strip()
    location = str(activity.get("location", "")).strip()
    title = str(activity.get("title", "")).strip()
    haystack = f"{title} {location}".strip()
    pools = [
        filter_real_candidates(state.get("attraction_candidates", []) or []),
        filter_real_candidates(state.get("food_candidates", []) or []),
        filter_real_candidates(
            state.get("hotel_options", []) or [],
            allow_sources={"llm_hotel"},
        ),
    ]
    for pool in pools:
        for item in pool:
            name = str(item.get("name", "")).strip()
            if not name or name in used:
                continue
            if source_id and str(item.get("id", "") or "").strip() == source_id:
                return item
            if location and name == location:
                return item
            if title and name == title:
                return item
            if haystack and name in haystack:
                return item
            if _candidate_name_match_score(haystack, name) >= 58:
                return item
    return None


def build_poi_queries(activity: Dict[str, Any], city: str) -> List[str]:
    queries: List[str] = []
    for value in (str(activity.get("location", "")).strip(), str(activity.get("title", "")).strip()):
        cleaned = clean_poi_search_query(value, city)
        if not cleaned:
            continue
        queries.extend([cleaned, f"{city}{cleaned}" if city and city not in cleaned else cleaned])
    return dedupe(queries)[:4]


def pick_best_poi(
    candidates: Sequence[Dict[str, Any]],
    activity: Dict[str, Any],
    city: str,
    used_poi_names: Iterable[str],
) -> Dict[str, Any] | None:
    used = set(used_poi_names)
    location = str(activity.get("location", "")).strip()
    title = str(activity.get("title", "")).strip()
    best: Dict[str, Any] | None = None
    best_score = -1.0
    for item in candidates:
        if not candidate_has_real_source(item):
            continue
        name = str(item.get("name", "")).strip()
        if not name or name in used:
            continue
        cleaned_query = clean_poi_search_query(location or title, city)
        score = score_general_candidate(item, city, cleaned_query, hotel=False)
        if location and name == location:
            score += 5
        if title and name == title:
            score += 4
        if location and location in name:
            score += 2
        score += _candidate_name_match_score(f"{title} {location}", name) / 20
        if score > best_score:
            best = item
            best_score = score
    return best


def enrich_activity_with_poi(activity: Dict[str, Any], poi: Dict[str, Any], city: str) -> Dict[str, Any]:
    enriched = dict(activity)
    name = str(poi.get("name", "")).strip()
    if name:
        enriched["location"] = name
        if not enriched.get("title"):
            enriched["title"] = name
    lat = safe_float(poi.get("lat"), 0.0)
    lng = safe_float(poi.get("lng"), 0.0)
    if lat and lng:
        enriched["coordinates"] = {"lat": lat, "lng": lng}
        enriched["lat"] = lat
        enriched["lng"] = lng
    enriched.update(build_source_metadata(poi))
    detail_parts = [
        str(poi.get("description", "")).strip(),
        str(poi.get("address", "")).strip(),
        str(poi.get("opening_hours", "")).strip(),
    ]
    detail_parts = [part for part in detail_parts if part]
    if detail_parts:
        enriched["description"] = "；".join(detail_parts[:3])
    if poi.get("opening_hours") and not enriched.get("opening_hours"):
        enriched["opening_hours"] = poi.get("opening_hours")
    if poi.get("price_note") and not enriched.get("price_note"):
        enriched["price_note"] = poi.get("price_note")
    if poi.get("avg_cost") and not enriched.get("avg_cost"):
        enriched["avg_cost"] = safe_int(poi.get("avg_cost"), 0)
    if poi.get("price") and not enriched.get("reference_price"):
        enriched["reference_price"] = poi.get("price")
    if poi.get("image_url") and not enriched.get("image"):
        enriched["image"] = poi.get("image_url")
    if not enriched.get("story"):
        enriched["story"] = f"{name or city}来自 POI 查询结果。"
    return enriched


def build_image_queries(city: str, activity: Dict[str, Any], selected_poi: Dict[str, Any]) -> List[str]:
    return dedupe(
        [
            str(selected_poi.get("name", "")).strip(),
            f"{city} {selected_poi.get('name', '')}".strip(),
            str(activity.get("location", "")).strip(),
            str(activity.get("title", "")).strip(),
        ]
    )


def build_local_summary(state: Dict[str, Any]) -> str:
    city = state.get("city", "")
    days = int(state.get("days", 0) or len(state.get("plan", []) or []))
    lines = [f"# {city} {days}天行程规划", ""]
    for day in state.get("plan", []) or []:
        lines.append(f"## Day {day.get('day', '')}")
        if day.get("theme"):
            lines.append(f"- 主题：{day.get('theme')}")
        if day.get("summary"):
            lines.append(f"- 概览：{day.get('summary')}")
        hotel = day.get("hotel_recommendation") or {}
        if hotel.get("name"):
            lines.append(f"- 酒店：{hotel.get('name')} ({hotel.get('address', '')})")
        highlights: List[str] = []
        seen_locations: set[str] = set()
        for activity in day.get("activities", []) or []:
            location = str(activity.get("location", "")).strip()
            if not location or location in seen_locations:
                continue
            seen_locations.add(location)
            highlights.append(f"{activity.get('time', '')} {location}".strip())
            if len(highlights) >= 4:
                break
        if highlights:
            lines.append(f"- 安排：{' / '.join(highlights)}")
        lines.append("")
    budget = state.get("estimated_budget") or {}
    if budget:
        lines.append("## 预算")
        lines.append(f"- 总计：{budget.get('total', 0)} {budget.get('currency', 'CNY')}")
        lines.append(f"- 人均：{budget.get('per_person', 0)} {budget.get('currency', 'CNY')}")
    return "\n".join(lines).strip()


def summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return {"final_output": build_local_summary(state)}


def _parse_start_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _candidate_name_match_score(raw: str, name: str) -> float:
    left = compact_name(clean_poi_search_query(raw))
    right = compact_name(name)
    if not left or not right:
        return 0.0
    if left == right:
        return 100.0
    if right in left:
        return 88.0
    if left in right:
        return 76.0
    overlap = len(set(left) & set(right))
    total = max(len(set(left) | set(right)), 1)
    return overlap / total * 70.0
