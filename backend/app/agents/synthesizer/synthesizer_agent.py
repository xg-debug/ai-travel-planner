import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.agents.shared import build_source_metadata, filter_real_candidates, normalize_itinerary
from app.orchestration.task_models import build_task_result
from app.orchestration.task_router import complete_task, get_ready_task_for_step
from app.services.weather_impact_service import weather_impact_service
from app.tools.amap_tools import search_hotels_tool, search_pois_tool

logger = logging.getLogger(__name__)


def _dedupe_candidates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    result: List[Dict[str, Any]] = []
    for item in items:
        name = str(item.get("name", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(item)
    return result


def _pop_next_unique(pool: List[Dict[str, Any]], used_names: set[str]) -> Dict[str, Any] | None:
    for index, item in enumerate(pool):
        name = str(item.get("name", "")).strip()
        if not name or name in used_names:
            continue
        used_names.add(name)
        return pool.pop(index)
    return None


def _supplement_real_candidates(
    current_items: List[Dict[str, Any]],
    *,
    city: str,
    queries: List[str],
    search_fn,
    min_count: int,
    allow_sources=None,
) -> List[Dict[str, Any]]:
    items = _dedupe_candidates(filter_real_candidates(current_items, allow_sources=allow_sources))
    if len(items) >= min_count:
        return items

    for query in queries:
        try:
            fetched = search_fn(query, city, 8)
        except Exception as exc:
            logger.warning("Supplement search failed city=%s query=%s error=%s", city, query, exc)
            continue
        merged = items + filter_real_candidates(fetched or [], allow_sources=allow_sources)
        items = _dedupe_candidates(merged)
        if len(items) >= min_count:
            break
    return items


def _build_activity(candidate: Dict[str, Any], time_text: str, title_suffix: str, activity_type: str) -> Dict[str, Any]:
    name = str(candidate.get("name", "")).strip()
    address = str(candidate.get("address", "")).strip()
    opening_hours = str(candidate.get("opening_hours", "")).strip()
    description_parts = [str(candidate.get("description", "")).strip(), address, opening_hours]
    description = "；".join([part for part in description_parts if part][:3])
    activity = {
        "time": time_text,
        "title": f"{name}{title_suffix}".strip(),
        "description": description,
        "type": activity_type,
        "location": name,
        "duration": 90,
        "cost_estimate": _safe_activity_cost(candidate, activity_type),
        "ticket_price": _safe_ticket_price(candidate, activity_type),
        "tips": str(candidate.get("tips", "")).strip(),
        "transportation": "步行/公共交通/网约车",
        "image": candidate.get("image_url"),
        "reason": candidate.get("reason", ""),
        "score": candidate.get("score"),
        "score_factors": candidate.get("score_factors", {}),
        "opening_hours": candidate.get("opening_hours", ""),
    }
    activity.update(build_source_metadata(candidate))
    return activity


def _safe_number(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        import re

        matched = re.search(r"\d+(?:\.\d+)?", str(value))
        return float(matched.group()) if matched else 0.0
    except Exception:
        return 0.0


def _safe_activity_cost(candidate: Dict[str, Any], activity_type: str) -> int:
    price = _safe_number(candidate.get("price"))
    if "美食" in activity_type or "餐" in activity_type:
        return int(price or 100)
    return int(price if price and price < 300 else 0)


def _safe_ticket_price(candidate: Dict[str, Any], activity_type: str) -> int:
    if "美食" in activity_type or "餐" in activity_type:
        return 0
    price = _safe_number(candidate.get("price"))
    return int(price if price and price < 300 else 0)


def _build_day_summary(activities: List[Dict[str, Any]], hotel: Dict[str, Any] | None) -> str:
    names: List[str] = []
    seen: set[str] = set()
    for activity in activities:
        name = str(activity.get("location", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= 3:
            break
    hotel_name = str((hotel or {}).get("name", "")).strip()
    summary = " - ".join([name for name in names if name])
    if hotel_name:
        summary += f"；入住 {hotel_name}" if summary else f"入住 {hotel_name}"
    return summary


def _parse_date(start_date: str | None, index: int) -> str | None:
    if not start_date:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return (datetime.strptime(start_date, fmt).date() + timedelta(days=index)).isoformat()
        except ValueError:
            continue
    return None


def _build_real_itinerary(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    days = int(state["days"])
    city = state["city"]
    attractions = _supplement_real_candidates(
        list(state.get("scored_attractions") or state.get("attraction_candidates", []) or []),
        city=city,
        queries=[f"{city}热门景点", f"{city}城市地标", f"{city}博物馆", f"{city}历史街区"],
        search_fn=search_pois_tool,
        min_count=2,
    )
    foods = _supplement_real_candidates(
        list(state.get("scored_foods") or state.get("food_candidates", []) or []),
        city=city,
        queries=[f"{city}本地特色美食", f"{city}老字号美食", f"{city}代表性小吃", f"{city}高评分特色餐厅", f"{city}美食街区"],
        search_fn=search_pois_tool,
        min_count=2,
    )
    hotels = _supplement_real_candidates(
        list(state.get("scored_hotels") or state.get("hotel_options", []) or []),
        city=city,
        queries=[f"{city}市中心酒店", f"{city}交通便利酒店", f"{city}高评分酒店"],
        search_fn=search_hotels_tool,
        min_count=1,
        allow_sources={"hotel", "agentichotel", "geo", "amap"},
    )

    if len(attractions) < 2:
        raise RuntimeError("真实景点候选不足，无法生成可信行程")
    if len(foods) < 2:
        raise RuntimeError("真实餐饮候选不足，无法生成可信行程")
    if not hotels:
        raise RuntimeError("真实酒店候选为空，无法生成可信行程")

    itinerary: List[Dict[str, Any]] = []
    remaining_attractions = list(attractions)
    remaining_foods = list(foods)
    used_attraction_names: set[str] = set()

    for index in range(days):
        feature_food = foods[index % len(foods)]
        secondary_food = foods[(index + 1) % len(foods)]
        morning = _pop_next_unique(remaining_attractions, used_attraction_names)
        afternoon = _pop_next_unique(remaining_attractions, used_attraction_names)
        evening_attraction = _pop_next_unique(remaining_attractions, used_attraction_names)
        evening = evening_attraction
        hotel = hotels[index % len(hotels)]

        weather_advice = weather_impact_service.build_weather_advice(index, state.get("weather_impacts", []) or [])
        activities: List[Dict[str, Any]] = []
        if morning:
            activities.append(_build_activity(morning, "09:30-11:30", "", "景点游览"))
        activities.append(_build_activity(feature_food, "12:00-13:30", "当地特色美食", "美食餐饮"))
        if afternoon:
            activities.append(_build_activity(afternoon, "14:00-17:00", "", "景点游览"))
        activities.append(_build_activity(secondary_food, "17:30-19:00", "顺路美食补给", "美食餐饮"))
        if evening:
            activities.append(
                _build_activity(
                    evening,
                    "19:30-21:00",
                    "晚间安排",
                    "休闲体验",
                )
            )

        itinerary.append(
            {
                "day": index + 1,
                "date": _parse_date(state.get("start_date"), index),
                "theme": f"{state['city']}真实地点串联游",
                "summary": _build_day_summary(activities, hotel),
                "weather_advice": weather_advice,
                "hotel_recommendation": {
                    "name": hotel.get("name", ""),
                    "price_estimate": hotel.get("price"),
                    "address": hotel.get("address", ""),
                    "reason": hotel.get("reason") or "基于真实酒店搜索结果选择的住宿候选。",
                    "score": hotel.get("score"),
                    "source": hotel.get("source", ""),
                    "source_id": hotel.get("id", ""),
                },
                "activities": activities,
            }
        )
    return itinerary


def synthesizer_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Synthesizing itinerary for %s (%s days)", state["city"], state["days"])
    task = get_ready_task_for_step(state, "synthesizer_agent")
    if not task:
        raise RuntimeError("synthesizer 任务未就绪")

    itinerary = normalize_itinerary(_build_real_itinerary(state), state)
    return {
        "draft_plan": itinerary,
        "plan": itinerary,
        "reflection_context": {},
        **complete_task(
            state,
            "synthesizer_agent",
            build_task_result(
                output={"day_count": len(itinerary)},
                metrics={"day_count": len(itinerary)},
                quality={"status": "draft_ready"},
                summary=f"已基于真实候选结果生成 {len(itinerary)} 天 itinerary 草案。",
            ),
        ),
    }
