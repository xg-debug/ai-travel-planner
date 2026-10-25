from __future__ import annotations

from typing import Any, Dict, List, Sequence

from app.domain.travel_domain import normalize_image_url
from app.trip_planning.candidates import dedupe_candidates_by_name, image_quality_score
from app.trip_planning.utils import compact_name


def build_recommendation_from_candidates(
    city: str,
    title: str,
    category: str,
    candidates: Sequence[Dict[str, Any]],
    reasoning: str,
) -> Dict[str, Any]:
    top_candidates = _dedupe_recommendation_candidates(
        [item for item in dedupe_candidates_by_name(list(candidates), city) if item.get("name")],
        city,
    )
    return {
        "type": category,
        "title": title,
        "items": [str(item.get("name", "")).strip() for item in top_candidates],
        "item_details": [_recommendation_item_detail(item) for item in top_candidates],
        "description": f"基于 {city} 的查询结果筛出的 {category}候选。",
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
            key = compact_name(name, city)
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
        next_recommendation["items"] = next_items
        next_recommendation["item_details"] = next_details
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
        "avg_cost",
        "price_text",
        "price_unit",
        "price_source",
        "price_confidence",
        "price_note",
        "display_rating",
        "score",
        "score_factors",
        "reason",
        "reason_tags",
        "description",
        "opening_hours",
        "best_time",
        "tips",
        "source",
    ):
        value = item.get(key)
        if value not in (None, "", []):
            detail[key] = value
    image_url = normalize_image_url(item.get("image_url") or item.get("image"))
    if image_url:
        detail["image_url"] = image_url
        detail["image_source_id"] = str(item.get("id") or item.get("source_id") or "").strip()
        detail["image_source_name"] = str(item.get("name") or item.get("title") or "").strip()
    return detail


def _dedupe_recommendation_candidates(items: Sequence[Dict[str, Any]], city: str = "") -> List[Dict[str, Any]]:
    best_by_key: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for item in items:
        key = _recommendation_display_key(item, city)
        if not key:
            continue
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = dict(item)
            order.append(key)
            continue
        if _display_quality(item) > _display_quality(current):
            best_by_key[key] = dict(item)
    return [best_by_key[key] for key in order if key in best_by_key]


def _recommendation_display_key(item: Dict[str, Any], city: str = "") -> str:
    raw_name = str(item.get("name") or item.get("title") or "").strip()
    if city:
        raw_name = raw_name.replace(city, "")
    if not raw_name:
        return ""
    import re

    parent_raw = re.split(r"[-—–·]", raw_name)[0]
    parent = compact_name(parent_raw)
    if parent and any(token in parent_raw for token in ("风景名胜区", "风景区", "景区", "公园", "度假区", "古镇", "古城")):
        return parent
    name = compact_name(raw_name)
    return re.sub(r"(游客中心|售票处|停车场|入口|出口|服务中心)$", "", name)


def _display_quality(item: Dict[str, Any]) -> float:
    def number(value: Any) -> float:
        try:
            return float(value or 0)
        except Exception:
            return 0.0

    return (
        number(item.get("score"))
        + number(item.get("rating")) * 10
        + image_quality_score(item)
        + (2 if item.get("opening_hours") else 0)
    )


def _recommendation_item_name(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("title") or "").strip()
    return str(item or "").strip()


def _find_recommendation_detail(details: Sequence[Any], name: str, city: str = "") -> Dict[str, Any] | None:
    target = compact_name(name, city)
    if not target:
        return None
    for detail in details or []:
        if not isinstance(detail, dict):
            continue
        detail_key = compact_name(detail.get("name") or detail.get("title"), city)
        if detail_key and (detail_key == target or detail_key in target or target in detail_key):
            return detail
    return None
