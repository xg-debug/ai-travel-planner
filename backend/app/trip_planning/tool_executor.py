from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Iterable, List

from app.core.llm import invoke_llm_with_fallback
from app.domain import travel_domain_service
from app.trip_planning.budget import budget_node
from app.trip_planning.intercity_transport import plan_intercity_transport
from app.trip_planning.risk_notices import risk_notice_node
from app.trip_planning.weather_impact import weather_tool_step
from app.trip_planning.candidates import (
    dedupe_candidates_by_name,
    filter_real_candidates,
    normalize_search_query,
    score_general_candidate,
)
from app.trip_planning.prompts import build_hotel_prompt
from app.trip_planning.recommendations import build_recommendation_from_candidates
from app.trip_planning.utils import dedupe, extract_json_block

logger = logging.getLogger(__name__)


class TripPlanningToolbox:
    def execute(self, state: Dict[str, Any], actions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        updates: Dict[str, Any] = {"tool_results": dict(state.get("tool_results", {}) or {})}
        for action in actions or []:
            name = str((action or {}).get("name") or "").strip()
            args = (action or {}).get("args") or {}
            if not name:
                continue
            try:
                result = self.execute_one(name, args if isinstance(args, dict) else {}, {**state, **updates})
            except Exception as exc:
                logger.warning("Trip planning tool failed name=%s error=%s", name, exc)
                result = {"error": str(exc)}
            updates["tool_results"][name] = result
            _merge_update(updates, result)
        return updates

    def execute_one(self, name: str, args: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        if name == "get_weather":
            return weather_tool_step({**state, "city": args.get("city") or state.get("city"), "days": args.get("days") or state.get("days")})
        if name == "search_attractions":
            return self.search_attractions(state, args)
        if name == "search_foods":
            return self.search_foods(state, args)
        if name == "recommend_hotels":
            return self.recommend_hotels(state, args)
        if name == "plan_transport":
            return self.plan_transport(state)
        raise ValueError(f"未知旅行规划工具：{name}")

    def search_attractions(self, state: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        city = str(state.get("city") or "").strip()
        queries = _normalize_queries(args.get("queries"), city, fallback=[f"{city}热门景点", f"{city}特色街区", f"{city}自然风光"])
        candidates = _search_many(city, queries, size=8)
        candidates = _rank_candidates(candidates, city, queries, hotel=False)
        existing = list(state.get("attraction_candidates", []) or [])
        merged = dedupe_candidates_by_name(existing + candidates, city)[: max(24, int(state.get("days", 1) or 1) * 8)]
        recommendation = build_recommendation_from_candidates(city, "景点推荐", "景点", merged[:12], "根据用户偏好和真实 POI 查询结果筛选。")
        return {
            "attraction_candidates": merged,
            "recommendations": _append_recommendation(state.get("recommendations", []), recommendation),
        }

    def search_foods(self, state: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        city = str(state.get("city") or "").strip()
        queries = _normalize_queries(args.get("queries"), city, fallback=[f"{city}本地特色美食", f"{city}老字号餐厅", f"{city}美食街"])
        candidates = [_item for _item in _search_many(city, queries, size=8) if not _is_blocked_food(_item)]
        candidates = _rank_candidates(candidates, city, queries, hotel=False)
        existing = list(state.get("food_candidates", []) or [])
        merged = dedupe_candidates_by_name(existing + candidates, city)[: max(18, int(state.get("days", 1) or 1) * 6)]
        recommendation = build_recommendation_from_candidates(city, "美食推荐", "美食", merged[:10], "排除食堂和内部餐饮后，优先保留本地特色餐饮。")
        return {
            "food_candidates": merged,
            "recommendations": _append_recommendation(state.get("recommendations", []), recommendation),
        }

    def recommend_hotels(self, state: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        count = max(3, min(int(args.get("count") or 5), 8))
        areas = [str(item).strip() for item in (args.get("areas") or []) if str(item).strip()]
        response = invoke_llm_with_fallback(
            build_hotel_prompt(state, areas, count),
            temperature=0.35,
            max_tokens=1800,
            request_timeout=35,
        )
        parsed = extract_json_block(getattr(response, "content", response)) or {}
        hotels = parsed.get("hotels") if isinstance(parsed, dict) else []
        normalized = _normalize_llm_hotels(hotels or [], state, count)
        existing = list(state.get("hotel_options", []) or [])
        merged = dedupe_candidates_by_name(existing + normalized, str(state.get("city", "")))[:count]
        recommendation = build_recommendation_from_candidates(
            str(state.get("city", "")),
            "酒店推荐",
            "住宿",
            merged,
            "由 LLM 根据住宿档位、预算、行程区域生成，价格为参考区间。",
        )
        return {
            "hotel_options": merged,
            "recommendations": _append_recommendation(state.get("recommendations", []), recommendation),
        }

    def plan_transport(self, state: Dict[str, Any]) -> Dict[str, Any]:
        intercity = plan_intercity_transport(
            state.get("departure_city"),
            state.get("city"),
            int(state.get("travelers") or 1),
            start_date=state.get("start_date"),
            outbound_departure_datetime=state.get("outbound_departure_datetime"),
            return_arrival_datetime=state.get("return_arrival_datetime"),
            days=int(state.get("days") or 1),
            budget_amount=state.get("budget_amount"),
            budget_level=state.get("budget"),
            preferences=state.get("preferences") or [],
        )
        return {"transport_plan": {"intercity_transport": intercity}, "intercity_transport": intercity}


def finalize_budget_and_risk(state: Dict[str, Any]) -> Dict[str, Any]:
    budget_update = budget_node(state)
    next_state = {**state, **budget_update}
    risk_update = risk_notice_node(next_state)
    return {**budget_update, **risk_update}


def _search_many(city: str, queries: List[str], size: int) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(queries)))) as pool:
        futures = {pool.submit(travel_domain_service.search_pois, query, city, 1, size): query for query in queries}
        for future in as_completed(futures):
            query = futures[future]
            try:
                for item in future.result() or []:
                    if isinstance(item, dict):
                        next_item = dict(item)
                        next_item["_query"] = query
                        results.append(next_item)
            except Exception as exc:
                logger.warning("POI search failed city=%s query=%s error=%s", city, query, exc)
    return filter_real_candidates(results, allow_sources={"geo", "amap", "amap_mcp_sse", "tencent"})


def _rank_candidates(items: List[Dict[str, Any]], city: str, queries: List[str], hotel: bool) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for item in items:
        query = str(item.get("_query") or (queries[0] if queries else "")).strip()
        next_item = dict(item)
        next_item["score"] = round(score_general_candidate(next_item, city, query, hotel=hotel), 2)
        ranked.append(next_item)
    return sorted(ranked, key=lambda item: float(item.get("score") or 0), reverse=True)


def _normalize_queries(value: Any, city: str, fallback: List[str]) -> List[str]:
    raw = value if isinstance(value, list) else []
    queries: List[str] = []
    for item in raw:
        queries.extend(normalize_search_query(str(item or ""), city))
    if not queries:
        queries = fallback
    return dedupe(queries)[:10]


def _normalize_llm_hotels(items: List[Dict[str, Any]], state: Dict[str, Any], count: int) -> List[Dict[str, Any]]:
    city = str(state.get("city") or "").strip()
    preference = str(state.get("accommodation_preference") or "mid-range")
    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(items[:count]):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        price = item.get("price_estimate") or item.get("price") or _default_hotel_price_range(preference)
        normalized.append(
            {
                "id": str(item.get("id") or f"llm_hotel_{index + 1}"),
                "name": name,
                "address": str(item.get("address") or city),
                "type": "酒店",
                "rating": float(item.get("rating") or 0),
                "price": str(price),
                "price_estimate": str(price),
                "budget_price_per_room": int(_safe_number(item.get("budget_price_per_room")) or _default_hotel_budget_price(preference)),
                "price_is_estimated": True,
                "reason": str(item.get("reason") or _hotel_reason(preference)),
                "lat": float(item.get("lat") or 0),
                "lng": float(item.get("lng") or 0),
                "source": "llm_hotel",
            }
        )
    if normalized:
        return normalized
    return [
        {
            "id": "llm_hotel_1",
            "name": f"{city}核心游览区中档酒店",
            "address": f"{city}核心游览区",
            "type": "酒店",
            "price": _default_hotel_price_range(preference),
            "price_estimate": _default_hotel_price_range(preference),
            "budget_price_per_room": _default_hotel_budget_price(preference),
            "price_is_estimated": True,
            "reason": _hotel_reason(preference),
            "source": "llm_hotel",
        }
    ]


def _default_hotel_price_range(preference: str) -> str:
    if preference == "budget":
        return "约 180-300 元/间夜（参考）"
    if preference == "luxury":
        return "约 700-1200 元/间夜（参考）"
    return "约 350-600 元/间夜（参考）"


def _default_hotel_budget_price(preference: str) -> int:
    if preference == "budget":
        return 240
    if preference == "luxury":
        return 900
    return 450


def _hotel_reason(preference: str) -> str:
    label = {"budget": "经济", "mid-range": "中档", "luxury": "高档"}.get(preference, "中档")
    return f"适合{label}预算游客，优先选择靠近主要游览区、晚间餐饮和公共交通的住宿。"


def _is_blocked_food(item: Dict[str, Any]) -> bool:
    text = " ".join(str(item.get(key, "") or "") for key in ("name", "address", "type", "description"))
    blocked = ("食堂", "餐厅(内部)", "内部餐厅", "单位餐厅", "学校餐厅", "大学", "学院", "校区")
    return any(token in text for token in blocked)


def _append_recommendation(existing: Any, item: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = [rec for rec in (existing or []) if isinstance(rec, dict)]
    title = str(item.get("title") or "").strip()
    return [rec for rec in items if str(rec.get("title") or "").strip() != title] + [item]


def _merge_update(target: Dict[str, Any], update: Dict[str, Any]) -> None:
    for key, value in (update or {}).items():
        if key == "recommendations":
            target[key] = value
            continue
        if value not in (None, "", [], {}):
            target[key] = value


def _safe_number(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except Exception:
        return 0.0
