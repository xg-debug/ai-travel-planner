from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Sequence

from app.core.config import settings


PREFERENCE_ALIASES = {
    "文化": "culture",
    "人文": "culture",
    "历史": "culture",
    "美食": "food",
    "餐饮": "food",
    "小吃": "food",
    "自然": "nature",
    "户外": "nature",
    "购物": "shopping",
    "拍照": "photography",
    "摄影": "photography",
    "亲子": "family",
    "culture": "culture",
    "food": "food",
    "nature": "nature",
    "shopping": "shopping",
    "photography": "photography",
    "family": "family",
}

REAL_DATA_SOURCES = {"geo", "hotel", "agentichotel", "amap", "tencent", "unsplash"}

ACTIVITY_QUERY_WORDS = (
    "探索",
    "探秘",
    "攀登",
    "登高",
    "瞻仰",
    "漫步",
    "扫街",
    "打卡",
    "体验",
    "游览",
    "观光",
    "轻徒步",
    "徒步",
    "咖啡时光",
    "夜市扫街",
    "外观光",
)


def dedupe(values: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def dedupe_candidates_by_name(items: Sequence[Dict[str, Any]], city: str = "") -> List[Dict[str, Any]]:
    best_by_key: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        key = _dedupe_name_key(name, city)
        if not key:
            continue
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = dict(item)
            order.append(key)
            continue
        if _candidate_quality(item) > _candidate_quality(current):
            best_by_key[key] = dict(item)
    return [best_by_key[key] for key in order if key in best_by_key]


def normalize_preferences(preferences: Sequence[str]) -> List[str]:
    normalized: List[str] = []
    for item in preferences or []:
        text = str(item or "").strip().lower()
        if not text:
            continue
        mapped = PREFERENCE_ALIASES.get(text, text)
        if mapped not in normalized:
            normalized.append(mapped)
    return normalized


def normalize_search_query(query: str, city: str) -> List[str]:
    text = str(query or "").strip()
    if not text:
        return []
    variants = [text]
    if city and city not in text:
        variants.append(f"{city}{text}")
        variants.append(f"{city} {text}")
    compact = re.sub(r"\s+", "", text)
    if compact and compact != text:
        variants.append(compact)
        if city and city not in compact:
            variants.append(f"{city}{compact}")
    return dedupe(variants)


def clean_poi_search_query(value: Any, city: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if city:
        text = text.replace(city, "")
    text = re.sub(r"[（(].*?[)）]", "", text)
    for word in ACTIVITY_QUERY_WORDS:
        text = text.replace(word, "")
    text = re.sub(r"(之旅|路线|行程|安排|时光|半日|一日|上午|下午|夜游)$", "", text)
    text = re.sub(r"[，。；;、/|]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_query_agent_fallback(state: Dict[str, Any]) -> Dict[str, Any]:
    city = str(state.get("city", "")).strip()
    preferences = normalize_preferences(state.get("preferences", []) or [])
    query = str(state.get("query", "")).strip()

    attraction_queries = [f"{city}热门景点", f"{city}城市地标", f"{city}高评分景点"]
    if "culture" in preferences:
        attraction_queries.extend([f"{city}博物馆", f"{city}历史街区"])
    if "nature" in preferences:
        attraction_queries.extend([f"{city}城市公园", f"{city}风景区"])
    if "shopping" in preferences:
        attraction_queries.append(f"{city}特色商圈")
    if "photography" in preferences:
        attraction_queries.append(f"{city}夜景地标")
    if "family" in preferences:
        attraction_queries.append(f"{city}亲子景点")

    hotel_queries = [f"{city}市中心酒店", f"{city}交通便利酒店", f"{city}高评分酒店"]
    food_queries = [f"{city}本地特色美食", f"{city}老字号美食", f"{city}代表性小吃", f"{city}高评分特色餐厅", f"{city}美食街区"]

    travel_style_parts: List[str] = []
    if "food" in preferences:
        travel_style_parts.append("美食体验")
    if "culture" in preferences:
        travel_style_parts.append("城市人文")
    if "nature" in preferences:
        travel_style_parts.append("轻户外")
    if "shopping" in preferences:
        travel_style_parts.append("休闲逛街")
    if not travel_style_parts:
        travel_style_parts.append("城市经典游")

    return {
        "travel_style": "、".join(travel_style_parts),
        "planning_focus": query or f"围绕{city}真实候选地点生成顺路、可执行的行程",
        "attraction_queries": dedupe(attraction_queries)[:8],
        "food_queries": dedupe(food_queries)[:8],
        "hotel_queries": dedupe(hotel_queries)[:6],
        "must_have": dedupe(list(preferences))[:8],
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def score_general_candidate(item: Dict[str, Any], city: str, query: str, hotel: bool = False) -> float:
    name = str(item.get("name", "")).strip()
    address = str(item.get("address", "")).strip()
    score = _safe_float(item.get("rating"), 0.0)

    if name and query and query.replace(city, "").strip() in name:
        score += 2.5
    if city and city in address:
        score += 0.8
    if item.get("lat") not in (None, 0, 0.0) and item.get("lng") not in (None, 0, 0.0):
        score += 0.6
    if item.get("image_url"):
        score += 0.3
    if hotel:
        price = str(item.get("price", "")).strip()
        if price:
            score += 0.4
    else:
        if str(item.get("opening_hours", "")).strip():
            score += 0.2
    return score


def candidate_has_real_source(item: Dict[str, Any], *, allow_sources: Iterable[str] | None = None) -> bool:
    source = str(item.get("source", "")).strip().lower()
    allowed = set(allow_sources or REAL_DATA_SOURCES)
    if not source or source not in allowed:
        return False

    name = str(item.get("name", "")).strip()
    item_id = str(item.get("id", "")).strip()
    has_coordinates = item.get("lat") not in (None, "", 0, 0.0) and item.get("lng") not in (None, "", 0, 0.0)
    return bool(name and (item_id or has_coordinates))


def filter_real_candidates(
    items: Sequence[Dict[str, Any]],
    *,
    allow_sources: Iterable[str] | None = None,
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not candidate_has_real_source(item, allow_sources=allow_sources):
            continue
        filtered.append(dict(item))
    return dedupe_candidates_by_name(filtered)


def build_source_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    source = str(item.get("source", "")).strip()
    metadata = {
        "source": source,
        "source_id": str(item.get("id", "")).strip(),
    }
    if item.get("lat") not in (None, "", 0, 0.0) and item.get("lng") not in (None, "", 0, 0.0):
        metadata["coordinates"] = {
            "lat": _safe_float(item.get("lat"), 0.0),
            "lng": _safe_float(item.get("lng"), 0.0),
        }
    return metadata


def build_recommendation_from_candidates(
    city: str,
    title: str,
    category: str,
    candidates: Sequence[Dict[str, Any]],
    reasoning: str,
) -> Dict[str, Any]:
    top_candidates = [item for item in dedupe_candidates_by_name(list(candidates), city)[:5] if item.get("name")]
    top_items = [str(item.get("name", "")).strip() for item in top_candidates]
    return {
        "type": category,
        "title": title,
        "items": top_items,
        "item_details": [_recommendation_item_detail(item) for item in top_candidates],
        "description": f"基于 {city} 的真实查询结果筛出的 {category}候选。",
        "reasoning": reasoning,
        "best_time": "",
        "price_range": "",
        "tips": "",
    }


def dedupe_recommendations(recommendations: Sequence[Dict[str, Any]], city: str = "") -> List[Dict[str, Any]]:
    seen_global: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    for recommendation in recommendations or []:
        if not isinstance(recommendation, dict):
            continue
        items = list(recommendation.get("items") or [])
        details = list(recommendation.get("item_details") or recommendation.get("itemDetails") or [])
        next_items: List[Any] = []
        next_details: List[Dict[str, Any]] = []
        seen_local: set[str] = set()
        for item in items:
            name = _recommendation_item_name(item)
            key = _dedupe_name_key(name, city)
            if not key or key in seen_local or key in seen_global:
                continue
            seen_local.add(key)
            seen_global.add(key)
            next_items.append(item)
            detail = item if isinstance(item, dict) else _find_recommendation_detail(details, name, city)
            if isinstance(detail, dict):
                next_details.append(dict(detail))
        if not next_items:
            continue
        next_recommendation = dict(recommendation)
        next_recommendation["items"] = next_items[:5]
        next_recommendation["item_details"] = next_details[:5]
        cleaned.append(next_recommendation)
    return cleaned


def _recommendation_item_detail(item: Dict[str, Any]) -> Dict[str, Any]:
    detail: Dict[str, Any] = {}
    for key in (
        "id",
        "name",
        "lat",
        "lng",
        "address",
        "type",
        "rating",
        "price",
        "price_text",
        "price_unit",
        "display_rating",
        "score",
        "score_factors",
        "reason",
        "reason_tags",
        "description",
        "opening_hours",
        "best_time",
        "tips",
        "image_url",
        "source",
    ):
        value = item.get(key)
        if value not in (None, "", []):
            detail[key] = value
    return detail


def extract_json_block(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    for candidate in (text, _slice_json_like(text)):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def _slice_json_like(text: str) -> str:
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start >= 0 and end > start:
            return text[start : end + 1]
    return ""


def extract_itinerary_data(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("itinerary", "plan", "days"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


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
            next_activity["duration"] = max(_safe_int(next_activity.get("duration"), 90), settings.MIN_ACTIVITY_DURATION)
            next_activity["cost_estimate"] = _safe_int(next_activity.get("cost_estimate"), 0)
            next_activity["ticket_price"] = _safe_int(next_activity.get("ticket_price"), 0)
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
        filter_real_candidates(state.get("hotel_options", []) or [], allow_sources={"hotel", "agentichotel", "geo", "amap"}),
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
    values = [
        str(activity.get("location", "")).strip(),
        str(activity.get("title", "")).strip(),
    ]
    queries: List[str] = []
    for value in values:
        cleaned = clean_poi_search_query(value, city)
        if not cleaned:
            continue
        queries.extend(normalize_search_query(cleaned, city))
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


def _candidate_name_match_score(raw: str, name: str) -> float:
    left = _compact_name(clean_poi_search_query(raw))
    right = _compact_name(name)
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


def _dedupe_name_key(value: Any, city: str = "") -> str:
    text = str(value or "").strip()
    if city:
        text = text.replace(city, "")
    return _compact_name(text)


def _candidate_quality(item: Dict[str, Any]) -> float:
    return (
        _safe_float(item.get("score"), 0.0)
        + _safe_float(item.get("rating"), 0.0) * 10
        + (3 if item.get("image_url") else 0)
        + (2 if item.get("address") else 0)
        + (2 if item.get("lat") not in (None, "", 0, 0.0) and item.get("lng") not in (None, "", 0, 0.0) else 0)
    )


def _recommendation_item_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("title") or "").strip()
    return str(item or "").strip()


def _find_recommendation_detail(details: Sequence[Any], name: str, city: str = "") -> Dict[str, Any] | None:
    target = _dedupe_name_key(name, city)
    if not target:
        return None
    for detail in details or []:
        if not isinstance(detail, dict):
            continue
        detail_key = _dedupe_name_key(detail.get("name") or detail.get("title"), city)
        if detail_key and (detail_key == target or detail_key in target or target in detail_key):
            return detail
    return None


def _compact_name(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", str(value or "")).lower()


def enrich_activity_with_poi(activity: Dict[str, Any], poi: Dict[str, Any], city: str) -> Dict[str, Any]:
    enriched = dict(activity)
    name = str(poi.get("name", "")).strip()
    if name:
        enriched["location"] = name
        if not enriched.get("title"):
            enriched["title"] = name
    coordinates = {
        "lat": _safe_float(poi.get("lat"), 0.0),
        "lng": _safe_float(poi.get("lng"), 0.0),
    }
    if coordinates["lat"] and coordinates["lng"]:
        enriched["coordinates"] = coordinates
        enriched["lat"] = coordinates["lat"]
        enriched["lng"] = coordinates["lng"]
    source_metadata = build_source_metadata(poi)
    enriched.update(source_metadata)
    address = str(poi.get("address", "")).strip()
    opening_hours = str(poi.get("opening_hours", "")).strip()
    description = str(poi.get("description", "")).strip()
    detail_parts = [part for part in [description, address, opening_hours] if part]
    if detail_parts:
        enriched["description"] = "；".join(detail_parts[:3])
    if poi.get("image_url") and not enriched.get("image"):
        enriched["image"] = poi.get("image_url")
    if not enriched.get("story"):
        enriched["story"] = f"{name or city}来自真实 POI 查询结果。"
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

    weather = (state.get("weather_data") or {}).get("forecast", []) or []
    if weather:
        lines.append("## 天气")
        for item in weather[:days]:
            date_text = str(item.get("date", "")).strip()
            condition = str(item.get("condition", "")).strip()
            temp = item.get("temperature", {}) or {}
            lines.append(f"- {date_text}: {condition}，{temp.get('min', '')}-{temp.get('max', '')}°C")
        lines.append("")

    intercity = state.get("intercity_transport") or (state.get("transport_plan") or {}).get("intercity_transport") or {}
    if intercity:
        lines.append("## 往返交通")
        for label, leg_key in (("去程", "outbound"), ("返程", "inbound")):
            leg = intercity.get(leg_key) or {}
            if not leg:
                continue
            lines.append(
                f"- {label}: {leg.get('from', '')} → {leg.get('to', '')}，"
                f"{leg.get('mode', '')}，{leg.get('duration_text', '')}，"
                f"约 {leg.get('cost_per_person', 0)} 元/人"
            )
        if intercity.get("total_cost"):
            lines.append(f"- 往返合计: {intercity.get('total_cost')} CNY")
        lines.append("")

    for day in state.get("plan", []) or []:
        lines.append(f"## Day {day.get('day', '')}")
        theme = str(day.get("theme", "")).strip()
        summary = str(day.get("summary", "")).strip()
        if theme:
            lines.append(f"- 主题：{theme}")
        if summary:
            lines.append(f"- 概览：{summary}")
        hotel = day.get("hotel_recommendation") or {}
        if hotel and hotel.get("name"):
            lines.append(f"- 酒店：{hotel.get('name')} ({hotel.get('address', '')})")
        highlights: List[str] = []
        seen_locations: set[str] = set()
        for activity in day.get("activities", []) or []:
            location = str(activity.get("location", "")).strip()
            if not location or location in seen_locations:
                continue
            seen_locations.add(location)
            time_text = str(activity.get("time", "")).strip()
            highlights.append(f"{time_text} {location}".strip())
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
        lines.append("")

    return "\n".join(lines).strip()
