from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence
from urllib.parse import urlparse

from app.domain.travel_domain import normalize_image_url

from app.trip_planning.utils import compact_name, dedupe


REAL_DATA_SOURCES = {"geo", "amap", "amap_mcp_sse", "amap_mcp", "tencent", "unsplash", "llm_hotel"}

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
    text = re.sub(r"(之旅|路线|行程|安排|时光|半日|一日|上午|下午|夜游)$", "", text)
    text = re.sub(r"[，。；;、/|]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_default_query_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    city = str(state.get("city", "")).strip()
    preferences = normalize_preferences(state.get("preferences", []) or [])
    query = str(state.get("query", "")).strip()
    attraction_queries = [f"{city}热门景点", f"{city}城市地标", f"{city}高评分景点"]
    if "culture" in preferences:
        attraction_queries.extend([f"{city}人文历史景点", f"{city}历史街区"])
    if "nature" in preferences:
        attraction_queries.extend([f"{city}城市公园", f"{city}自然风光"])
    if "shopping" in preferences:
        attraction_queries.append(f"{city}特色商圈")
    if "photography" in preferences:
        attraction_queries.append(f"{city}夜景地标")
    if "family" in preferences:
        attraction_queries.append(f"{city}亲子景点")
    food_queries = [f"{city}本地特色美食", f"{city}老字号美食", f"{city}代表性小吃", f"{city}高评分特色餐厅", f"{city}美食街区"]
    travel_style_parts = []
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
        "planning_focus": query or f"围绕{city}生成顺路、可执行的行程",
        "attraction_queries": dedupe(attraction_queries)[:8],
        "food_queries": dedupe(food_queries)[:8],
        "hotel_queries": [f"{city}住宿建议"],
        "must_have": dedupe(list(preferences))[:8],
    }


def dedupe_candidates_by_name(items: Sequence[Dict[str, Any]], city: str = "") -> List[Dict[str, Any]]:
    best_by_key: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        key = compact_name(name, city)
        if not key:
            continue
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = dict(item)
            order.append(key)
            continue
        if candidate_quality(item) > candidate_quality(current):
            best_by_key[key] = dict(item)
    return [best_by_key[key] for key in order if key in best_by_key]


def candidate_has_real_source(item: Dict[str, Any], *, allow_sources: Iterable[str] | None = None) -> bool:
    source = str(item.get("source", "")).strip().lower()
    allowed = set(allow_sources or REAL_DATA_SOURCES)
    if not source or source not in allowed:
        return False
    name = str(item.get("name", "")).strip()
    item_id = str(item.get("id", "")).strip()
    has_coordinates = item.get("lat") not in (None, "", 0, 0.0) and item.get("lng") not in (None, "", 0, 0.0)
    if source == "llm_hotel":
        return bool(name and item_id)
    return bool(name and (item_id or has_coordinates))


def filter_real_candidates(
    items: Sequence[Dict[str, Any]],
    *,
    allow_sources: Iterable[str] | None = None,
) -> List[Dict[str, Any]]:
    filtered = [
        dict(item)
        for item in items or []
        if isinstance(item, dict) and candidate_has_real_source(item, allow_sources=allow_sources)
    ]
    return dedupe_candidates_by_name(filtered)


def build_source_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
    source = str(item.get("source", "")).strip()
    metadata = {
        "source": source,
        "source_id": str(item.get("id", "")).strip(),
    }
    lat = safe_float(item.get("lat"), 0.0)
    lng = safe_float(item.get("lng"), 0.0)
    if lat and lng:
        metadata["coordinates"] = {"lat": lat, "lng": lng}
    return metadata


def score_general_candidate(item: Dict[str, Any], city: str, query: str, hotel: bool = False) -> float:
    name = str(item.get("name", "")).strip()
    address = str(item.get("address", "")).strip()
    score = safe_float(item.get("rating"), 0.0)
    if name and query and query.replace(city, "").strip() in name:
        score += 2.5
    if city and city in address:
        score += 0.8
    if item.get("lat") not in (None, 0, 0.0) and item.get("lng") not in (None, 0, 0.0):
        score += 0.6
    score += image_quality_score(item) / 10
    if hotel and str(item.get("price", "")).strip():
        score += 0.4
    elif str(item.get("opening_hours", "")).strip():
        score += 0.2
    return score


def candidate_quality(item: Dict[str, Any]) -> float:
    return (
        safe_float(item.get("score"), 0.0)
        + safe_float(item.get("rating"), 0.0) * 10
        + image_quality_score(item)
        + (2 if item.get("address") else 0)
        + (2 if item.get("lat") not in (None, "", 0, 0.0) and item.get("lng") not in (None, "", 0, 0.0) else 0)
    )


def image_quality_score(item: Dict[str, Any]) -> float:
    url = normalize_image_url(item.get("image_url") or item.get("image"))
    if not url:
        return 0.0
    host = urlparse(url).netloc.lower()
    score = 3.0
    if host.endswith("amap.com") or host.endswith("autonavi.com"):
        score += 2.0
    if any(token in url.lower() for token in ("placeholder", "default", "blank", "logo")):
        score -= 2.0
    return max(score, 0.0)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default
