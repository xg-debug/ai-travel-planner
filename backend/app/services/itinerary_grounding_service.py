from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, Iterable, List, Sequence

from app.agents.shared import filter_real_candidates, normalize_itinerary

logger = logging.getLogger(__name__)

MAX_REASONABLE_LEG_KM = 18.0
MAX_REASONABLE_DAY_KM = 45.0
OUTLIER_DISTANCE_KM = 16.0
DINNER_HOTEL_MAX_KM = 10.0
CLOSING_HOTEL_MAX_KM = 18.0
MEAL_ROUTE_MAX_KM = 12.0

HOTEL_ACTIVITY_TOKENS = (
    "入住",
    "办理入住",
    "酒店休息",
    "返回酒店",
    "回酒店",
    "住宿",
    "check-in",
    "check in",
)

TRANSPORT_TITLE_TOKENS = (
    "前往",
    "驱车",
    "打车",
    "乘车",
    "坐车",
    "自驾",
    "抵达",
    "出发",
    "返程",
    "返回",
    "上岛",
    "离岛",
    "交通",
    "路线",
)

ACTIVITY_WORDS = (
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

FOOD_TOKENS = ("早餐", "早午茶", "午餐", "晚餐", "餐", "美食", "小吃", "咖啡", "茶", "火锅", "面", "饭")

RETURN_TERMINAL_TOKENS = (
    "返程",
    "返回",
    "回程",
    "离开",
    "回到出发地",
    "返回出发地",
    "返抵",
    "返家",
)

RETURN_TRANSPORT_TOKENS = (
    "高铁",
    "动车",
    "火车",
    "飞机",
    "航班",
    "机场",
    "车站",
    "大巴",
    "客运",
    "铁路",
    "交通",
)

INTERCITY_ACTIVITY_TOKENS = (
    "城际交通",
    "大交通",
    "往返交通",
    "去程交通",
    "返程交通",
)

DAYTIME_POI_TOKENS = (
    "博物馆",
    "纪念馆",
    "展览馆",
    "展馆",
    "美术馆",
    "科技馆",
    "文化馆",
    "图书馆",
    "故居",
    "会馆",
    "祠堂",
    "寺",
    "塔",
)

NIGHT_SAFE_TOKENS = (
    "夜景",
    "夜市",
    "步行街",
    "商圈",
    "酒吧",
    "演出",
    "灯光",
    "广场",
    "江景",
    "河景",
    "散步",
)

EVENING_ACTIVITY_TOKENS = (
    "夜",
    "晚间",
    "夜景",
    "夜市",
    "演出",
    "灯光",
    "酒吧",
    "散步",
)


def ground_itinerary_with_real_pois(state: Dict[str, Any]) -> Dict[str, Any]:
    plan = normalize_itinerary(state.get("plan", []) or [], state)
    pools = _candidate_pools(state)
    used_names = _initial_used_names(plan)
    patch_actions: List[Dict[str, Any]] = []
    route_reports: List[Dict[str, Any]] = []
    intercity_transport = state.get("intercity_transport") or (state.get("transport_plan") or {}).get("intercity_transport") or {}
    outbound_leg = _intercity_leg(intercity_transport, "outbound")
    inbound_leg = _intercity_leg(intercity_transport, "inbound")

    grounded_plan: List[Dict[str, Any]] = []
    for day_index, day in enumerate(plan):
        next_day = dict(day)
        activities = []
        for item in day.get("activities", []) or []:
            activity = dict(item)
            if _is_synthetic_intercity_transport_activity(activity, outbound_leg, inbound_leg):
                patch_actions.append(
                    {
                        "day": day_index + 1,
                        "action": "remove_duplicate_intercity_transport",
                        "from": _activity_place_text(activity),
                    }
                )
                continue
            if _is_hotel_activity(activity):
                patch_actions.append(
                    {
                        "day": day_index + 1,
                        "action": "remove_hotel_activity",
                        "from": _activity_place_text(activity),
                    }
                )
                continue
            activities.append(activity)
        activities, return_terminal = _split_return_terminal_activities(
            activities,
            is_last_day=day_index == len(plan) - 1,
            day_no=day_index + 1,
            patch_actions=patch_actions,
        )
        center = _fallback_day_center(pools, day_index)
        hotel_candidate = _resolve_day_hotel(next_day, pools)
        hotel_coord = _candidate_coord(hotel_candidate or {}) or _hotel_coord(next_day.get("hotel_recommendation") or {})
        if hotel_candidate:
            next_day["hotel_recommendation"] = _apply_hotel_candidate(next_day.get("hotel_recommendation") or {}, hotel_candidate)
        if hotel_coord and not center:
            center = hotel_coord

        resolved: List[Dict[str, Any]] = []
        for activity in activities:
            category = _activity_category(activity)
            candidate = _match_activity_candidate(activity, pools, used_names, category)
            if not candidate:
                candidate = _pick_replacement_candidate(pools, category, used_names, center)
                if candidate:
                    patch_actions.append(
                        {
                            "day": day_index + 1,
                            "action": "replace_unresolved_poi",
                            "from": _activity_place_text(activity),
                            "to": candidate.get("name", ""),
                        }
                    )
            if candidate:
                activity = _apply_candidate(activity, candidate, category)
                _mark_name_used(used_names, candidate.get("name", ""))
            resolved.append(activity)

        activity_center = _best_day_center(resolved)
        if activity_center and next_day.get("hotel_recommendation") and _should_anchor_hotel_to_day_area(hotel_coord, activity_center):
            hotel_candidate = _pick_hotel_near_anchor(pools, activity_center)
            if hotel_candidate:
                candidate_coord = _candidate_coord(hotel_candidate)
                if candidate_coord and (not hotel_coord or _distance_km(candidate_coord, activity_center) + 5 < _distance_km(hotel_coord, activity_center)):
                    hotel_coord = candidate_coord
                    next_day["hotel_recommendation"] = _apply_hotel_candidate(next_day.get("hotel_recommendation") or {}, hotel_candidate)
                    patch_actions.append(
                        {
                            "day": day_index + 1,
                            "action": "anchor_hotel_to_day_area",
                            "to": hotel_candidate.get("name", ""),
                        }
                    )

        center = _best_day_center(resolved, hotel_coord) or activity_center or center
        repaired = _replace_route_outliers(resolved, pools, used_names, center, day_index, patch_actions)
        repaired = _repair_meals_near_route(repaired, pools, used_names, hotel_coord, day_index, patch_actions)
        repaired = _repair_dinner_near_hotel(repaired, pools, used_names, hotel_coord, day_index, patch_actions)
        repaired = _repair_closing_near_hotel(repaired, pools, used_names, hotel_coord, day_index, patch_actions)
        ordered = _order_day_route(repaired, hotel_coord)
        if not _has_evening_activity(ordered):
            ordered = _arrange_dinner_towards_hotel(ordered, hotel_coord)
        if [item.get("location") for item in ordered] != [item.get("location") for item in repaired]:
            patch_actions.append({"day": day_index + 1, "action": "reorder_day_route"})
        start_after = _leg_arrival_minutes(outbound_leg) + 45 if day_index == 0 and outbound_leg else None
        end_before = _leg_departure_minutes(inbound_leg) - 60 if day_index == len(plan) - 1 and inbound_leg else None
        ordered = _repair_time_incompatible_activities(
            ordered,
            pools,
            used_names,
            day_index,
            patch_actions,
            start_after_minutes=start_after,
            end_before_minutes=end_before,
        )
        ordered = _assign_route_times(ordered, start_after_minutes=start_after, end_before_minutes=end_before)
        if day_index == 0 and outbound_leg:
            ordered = [_transport_activity_from_leg(outbound_leg)] + ordered
            patch_actions.append({"day": day_index + 1, "action": "insert_outbound_transport"})
        if day_index == len(plan) - 1 and inbound_leg:
            ordered = _trim_activities_before_departure(ordered, _leg_departure_minutes(inbound_leg))
            ordered.append(_transport_activity_from_leg(inbound_leg))
            patch_actions.append({"day": day_index + 1, "action": "insert_inbound_transport"})
        elif return_terminal:
            ordered = _append_return_terminal(ordered, return_terminal)
        metrics = _route_metrics(ordered, hotel_coord)
        route_reports.append({"day": day_index + 1, **metrics})

        next_day["activities"] = ordered
        next_day["route_quality"] = metrics
        if ordered:
            next_day["summary"] = " - ".join(str(item.get("location", "")).strip() for item in ordered[:4] if item.get("location"))
        grounded_plan.append(next_day)

    grounded_plan = normalize_itinerary(grounded_plan, state)
    if patch_actions:
        logger.info("Grounded itinerary with real POIs patch_count=%s", len(patch_actions))
    return {
        "plan": grounded_plan,
        "draft_plan": grounded_plan,
        "reviewed_plan": grounded_plan,
        "route_quality": {"days": route_reports, "patch_count": len(patch_actions)},
        "route_patch_actions": patch_actions,
    }


def clean_poi_query(value: Any, city: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if city:
        text = text.replace(city, "")
    text = re.sub(r"[（(].*?[)）]", "", text)
    for word in ACTIVITY_WORDS:
        text = text.replace(word, "")
    text = re.sub(r"(之旅|路线|行程|安排|时光|半日|一日|上午|下午|夜游)$", "", text)
    text = re.sub(r"[，。；;、/|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _candidate_pools(state: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "attraction": filter_real_candidates(state.get("scored_attractions") or state.get("attraction_candidates") or []),
        "food": filter_real_candidates(state.get("scored_foods") or state.get("food_candidates") or []),
        "hotel": filter_real_candidates(
            state.get("scored_hotels") or state.get("hotel_options") or [],
            allow_sources={"hotel", "agentichotel", "geo", "amap", "tencent"},
        ),
    }


def _resolve_day_hotel(day: Dict[str, Any], pools: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any] | None:
    hotel = day.get("hotel_recommendation") or {}
    hotels = list(pools.get("hotel", []) or [])
    if not hotel or not hotels:
        return None

    source_id = str(hotel.get("source_id", "") or hotel.get("id", "") or "").strip()
    if source_id:
        for candidate in hotels:
            if str(candidate.get("id", "") or "").strip() == source_id:
                return dict(candidate)

    raw_texts = [
        str(hotel.get("name", "") or "").strip(),
        str(hotel.get("address", "") or "").strip(),
    ]
    best: Dict[str, Any] | None = None
    best_score = 0.0
    for candidate in hotels:
        name = str(candidate.get("name", "") or "").strip()
        address = str(candidate.get("address", "") or "").strip()
        if not name:
            continue
        score = max([_name_match_score(raw, name) for raw in raw_texts if raw] or [0.0])
        if address and any(address in raw or raw in address for raw in raw_texts if raw):
            score = max(score, 72.0)
        score += min(float(candidate.get("score", 0) or 0) / 100, 1.0)
        if score > best_score:
            best = dict(candidate)
            best_score = score
    return best if best_score >= 55 else None


def _apply_hotel_candidate(hotel: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    next_hotel = dict(hotel or {})
    if candidate.get("name"):
        next_hotel["name"] = candidate.get("name")
    if candidate.get("price") and not next_hotel.get("price_estimate"):
        next_hotel["price_estimate"] = candidate.get("price")
    if candidate.get("address"):
        next_hotel["address"] = candidate.get("address")
    if candidate.get("reason") and not next_hotel.get("reason"):
        next_hotel["reason"] = candidate.get("reason")
    if candidate.get("source"):
        next_hotel["source"] = candidate.get("source")
    if candidate.get("id"):
        next_hotel["source_id"] = candidate.get("id")
    if candidate.get("score") is not None:
        next_hotel["score"] = candidate.get("score")
    coord = _candidate_coord(candidate)
    if coord:
        lat, lng = coord
        next_hotel["coordinates"] = {"lat": lat, "lng": lng}
        next_hotel["lat"] = lat
        next_hotel["lng"] = lng
    return next_hotel


def _initial_used_names(plan: Sequence[Dict[str, Any]]) -> set[str]:
    # Start empty and mark places as they are accepted, so the first valid
    # occurrence is kept and later duplicates can be replaced.
    return set()


def _activity_category(activity: Dict[str, Any]) -> str:
    text = " ".join(
        str(activity.get(key, "") or "")
        for key in ("title", "type", "description", "location")
    )
    if any(token in text for token in FOOD_TOKENS):
        return "food"
    return "attraction"


def _is_hotel_activity(activity: Dict[str, Any]) -> bool:
    text = " ".join(
        str(activity.get(key, "") or "")
        for key in ("title", "type", "description", "location")
    ).lower()
    if not any(token.lower() in text for token in HOTEL_ACTIVITY_TOKENS):
        return False
    return any(token in text for token in ("酒店", "住宿", "民宿", "客栈", "宾馆", "hotel", "check"))


def _is_existing_intercity_transport_activity(activity: Dict[str, Any]) -> bool:
    if activity.get("is_intercity_transport"):
        return True
    text = _activity_text(activity)
    has_transport = any(token in text for token in RETURN_TRANSPORT_TOKENS)
    has_trip_edge = any(token in text for token in ("出发地", "目的地", "去程", "返程", "返回出发地", "回到出发地"))
    return has_transport and has_trip_edge


def _is_synthetic_intercity_transport_activity(
    activity: Dict[str, Any],
    outbound_leg: Dict[str, Any] | None = None,
    inbound_leg: Dict[str, Any] | None = None,
) -> bool:
    if _is_existing_intercity_transport_activity(activity):
        return True

    text = _activity_text(activity)
    title = str(activity.get("title") or "").strip()
    if any(token in text for token in INTERCITY_ACTIVITY_TOKENS):
        return True

    for leg in (outbound_leg, inbound_leg):
        if not leg:
            continue
        if _leg_city_pair_in_text(leg, text) and any(token in text for token in RETURN_TRANSPORT_TOKENS):
            return True

    has_route_connector = bool(re.search(r".+(至|到|→|->).+", title))
    return has_route_connector and any(token in title for token in ("交通", "车", "高铁", "动车", "火车", "飞机", "大巴"))


def _leg_city_pair_in_text(leg: Dict[str, Any], text: str) -> bool:
    from_city = _normalize_name(str(leg.get("from") or ""))
    to_city = _normalize_name(str(leg.get("to") or ""))
    normalized_text = _normalize_name(text)
    return bool(from_city and to_city and from_city in normalized_text and to_city in normalized_text)


def _intercity_leg(intercity_transport: Dict[str, Any], key: str) -> Dict[str, Any] | None:
    leg = intercity_transport.get(key) if isinstance(intercity_transport, dict) else None
    return leg if isinstance(leg, dict) and leg.get("from") and leg.get("to") else None


def _transport_activity_from_leg(leg: Dict[str, Any]) -> Dict[str, Any]:
    direction = str(leg.get("direction") or "")
    label = "去程" if direction == "outbound" else "返程"
    best_option = _leg_best_transport_option(leg)
    mode = str(best_option.get("mode") or leg.get("mode") or "城际交通").strip()
    from_city = str(leg.get("from") or "").strip()
    to_city = str(leg.get("to") or "").strip()
    from_terminal = str(best_option.get("from_terminal") or leg.get("from_terminal") or from_city).strip()
    to_terminal = str(best_option.get("to_terminal") or leg.get("to_terminal") or to_city).strip()
    departure_datetime = best_option.get("departure_datetime") or leg.get("departure_datetime")
    arrival_datetime = best_option.get("arrival_datetime") or leg.get("arrival_datetime")
    duration = int(_safe_float(best_option.get("duration_minutes") or leg.get("duration_minutes"), 0) or 0)
    cost = int(_safe_float(best_option.get("total_cost") or leg.get("total_cost"), 0) or 0)
    cost_per_person = int(_safe_float(best_option.get("cost_per_person") or leg.get("cost_per_person"), 0) or 0)
    transport_options = _leg_transport_options(leg, best_option)
    return {
        "time": _leg_time_range(leg),
        "title": f"{label}：{from_city} → {to_city}   {mode}",
        "description": f"{label}交通安排，{_datetime_text(departure_datetime)} 出发，{_datetime_text(arrival_datetime)} 到达，预计耗时 {best_option.get('duration_text') or leg.get('duration_text') or _format_duration(duration)}。",
        "type": "交通衔接",
        "location": f"{from_terminal} - {to_terminal}",
        "duration": max(duration, 30),
        "cost_estimate": cost,
        "ticket_price": 0,
        "tips": f"预估单人费用 {cost_per_person} 元，建议出行前核对实时车次、航班或路况。",
        "transportation": mode,
        "is_intercity_transport": True,
        "intercity_direction": direction,
        "departure_datetime": departure_datetime,
        "arrival_datetime": arrival_datetime,
        "from_terminal": from_terminal,
        "to_terminal": to_terminal,
        "cost_per_person": cost_per_person,
        "total_cost": cost,
        "best_transport_option": best_option,
        "transport_options": transport_options,
        "transport_alternatives": [dict(item) for item in transport_options[1:]],
        "source": leg.get("source", ""),
    }


def _leg_best_transport_option(leg: Dict[str, Any]) -> Dict[str, Any]:
    option = leg.get("best_option")
    if isinstance(option, dict) and option:
        return dict(option)
    options = leg.get("options")
    if isinstance(options, list):
        for item in options:
            if isinstance(item, dict) and item:
                return dict(item)
    return {
        "mode": leg.get("mode"),
        "from_terminal": leg.get("from_terminal") or leg.get("from"),
        "to_terminal": leg.get("to_terminal") or leg.get("to"),
        "departure_datetime": leg.get("departure_datetime"),
        "arrival_datetime": leg.get("arrival_datetime"),
        "departure_time": leg.get("departure_time"),
        "arrival_time": leg.get("arrival_time"),
        "duration_minutes": leg.get("duration_minutes"),
        "duration_text": leg.get("duration_text"),
        "cost_per_person": leg.get("cost_per_person"),
        "total_cost": leg.get("total_cost"),
        "currency": leg.get("currency") or "CNY",
        "reason": leg.get("note") or "",
        "recommended": True,
    }


def _leg_transport_options(leg: Dict[str, Any], best_option: Dict[str, Any]) -> List[Dict[str, Any]]:
    options: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in [best_option, *_option_list(leg.get("options")), *_option_list(leg.get("alternatives"))]:
        if not isinstance(item, dict) or not item:
            continue
        key = _transport_option_key(item)
        if key in seen:
            continue
        seen.add(key)
        options.append(dict(item))
    return options


def _option_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _transport_option_key(option: Dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(option.get("mode") or "").strip().lower(),
        str(option.get("from_terminal") or "").strip().lower(),
        str(option.get("to_terminal") or "").strip().lower(),
        str(option.get("departure_datetime") or "").strip(),
    )


def _leg_time_range(leg: Dict[str, Any]) -> str:
    best_option = _leg_best_transport_option(leg)
    departure = _time_from_datetime(best_option.get("departure_datetime") or leg.get("departure_datetime")) or str(best_option.get("departure_time") or leg.get("departure_time") or "").strip()
    arrival = _time_from_datetime(best_option.get("arrival_datetime") or leg.get("arrival_datetime")) or str(best_option.get("arrival_time") or leg.get("arrival_time") or "").strip()
    if departure and arrival:
        return f"{departure}-{arrival}"
    return departure or arrival or ""


def _datetime_text(value: Any) -> str:
    text = str(value or "").strip()
    return text or "时间待确认"


def _leg_departure_minutes(leg: Dict[str, Any] | None) -> int:
    if not leg:
        return 24 * 60
    return _minutes_from_datetime(leg.get("departure_datetime")) or _minutes_from_clock(leg.get("departure_time")) or 24 * 60


def _leg_arrival_minutes(leg: Dict[str, Any] | None) -> int:
    if not leg:
        return 9 * 60 + 30
    return _minutes_from_datetime(leg.get("arrival_datetime")) or _minutes_from_clock(leg.get("arrival_time")) or 9 * 60 + 30


def _time_from_datetime(value: Any) -> str:
    matched = re.search(r"(\d{1,2}):(\d{2})", str(value or ""))
    return f"{int(matched.group(1)):02d}:{matched.group(2)}" if matched else ""


def _minutes_from_datetime(value: Any) -> int | None:
    return _minutes_from_clock(_time_from_datetime(value))


def _minutes_from_clock(value: Any) -> int | None:
    matched = re.search(r"(\d{1,2}):(\d{2})", str(value or ""))
    if not matched:
        return None
    return int(matched.group(1)) * 60 + int(matched.group(2))


def _trim_activities_before_departure(activities: List[Dict[str, Any]], departure_minutes: int) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for activity in activities:
        end_minutes = _end_minutes(activity.get("time"))
        start_minutes = _minutes_from_clock(_start_time(activity.get("time")))
        compare_minutes = end_minutes if end_minutes is not None else start_minutes
        if compare_minutes is not None and compare_minutes > departure_minutes:
            continue
        result.append(activity)
    return result


def _split_return_terminal_activities(
    activities: List[Dict[str, Any]],
    *,
    is_last_day: bool,
    day_no: int,
    patch_actions: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, Any] | None]:
    if not is_last_day:
        return activities, None

    terminal_indexes = [index for index, activity in enumerate(activities) if _is_return_terminal_activity(activity)]
    if not terminal_indexes:
        return activities, None

    terminal_index = min(
        terminal_indexes,
        key=lambda index: (_start_hour(activities[index].get("time")) if _start_hour(activities[index].get("time")) is not None else 24.0, index),
    )
    terminal = dict(activities[terminal_index])
    terminal_hour = _start_hour(terminal.get("time"))
    kept: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []

    for index, activity in enumerate(activities):
        if index == terminal_index:
            continue
        activity_hour = _start_hour(activity.get("time"))
        remove_activity = index > terminal_index
        if terminal_hour is not None and activity_hour is not None:
            remove_activity = activity_hour > terminal_hour
        if remove_activity:
            removed.append(activity)
        else:
            kept.append(activity)

    if removed:
        patch_actions.append(
            {
                "day": day_no,
                "action": "remove_after_return_terminal",
                "removed": [_activity_place_text(activity) for activity in removed],
            }
        )
    return kept, terminal


def _is_return_terminal_activity(activity: Dict[str, Any]) -> bool:
    if _is_hotel_activity(activity):
        return False
    text = _activity_text(activity)
    has_return = any(token in text for token in RETURN_TERMINAL_TOKENS)
    has_transport = any(token in text for token in RETURN_TRANSPORT_TOKENS)
    return has_return and (has_transport or "返程" in text or "离开" in text)


def _activity_text(activity: Dict[str, Any]) -> str:
    return " ".join(
        str(activity.get(key, "") or "")
        for key in ("title", "type", "description", "location", "transportation", "tips", "opening_hours")
    )


def _match_activity_candidate(
    activity: Dict[str, Any],
    pools: Dict[str, List[Dict[str, Any]]],
    used_names: Iterable[str],
    category: str,
) -> Dict[str, Any] | None:
    source_id = str(activity.get("source_id", "") or activity.get("id", "") or "").strip()
    candidates = list(pools.get(category, []) or [])
    if category != "food":
        candidates += list(pools.get("food", []) or [])
    used = set(used_names)

    if source_id:
        for item in candidates:
            name = str(item.get("name", "") or "").strip()
            if str(item.get("id", "") or "").strip() == source_id and not _is_name_used(used, name):
                return dict(item)

    raw_texts = [
        str(activity.get("location", "") or "").strip(),
        str(activity.get("title", "") or "").strip(),
    ]
    best: Dict[str, Any] | None = None
    best_score = 0.0
    for item in candidates:
        name = str(item.get("name", "") or "").strip()
        if not name:
            continue
        if _is_name_used(used, name):
            continue
        raw_scores = [_name_match_score(raw, name) for raw in raw_texts if raw]
        score = max(raw_scores) if raw_scores else 0.0
        score += min(float(item.get("score", 0) or 0) / 100, 1.0)
        if score > best_score:
            best = dict(item)
            best_score = score
    return best if best_score >= 55 else None


def _name_match_score(raw: str, name: str) -> float:
    raw_norm = _normalize_name(raw)
    name_norm = _normalize_name(name)
    if not raw_norm or not name_norm:
        return 0.0
    if raw_norm == name_norm:
        return 100.0
    if name_norm in raw_norm:
        return 88.0
    if raw_norm in name_norm:
        return 76.0
    overlap = len(set(raw_norm) & set(name_norm))
    base = max(len(set(raw_norm) | set(name_norm)), 1)
    return overlap / base * 70.0


def _normalize_name(value: str) -> str:
    text = clean_poi_query(value)
    text = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
    for suffix in ("景区", "公园", "商业中心", "步行街", "文化广场"):
        if text.endswith(suffix) and len(text) > len(suffix) + 2:
            break
    return text.lower()


def _name_key(value: Any) -> str:
    return _normalize_name(str(value or ""))


def _is_name_used(used_names: Iterable[str], name: Any) -> bool:
    key = _name_key(name)
    if not key:
        return False
    return key in {_name_key(item) for item in used_names}


def _mark_name_used(used_names: set[str], name: Any) -> None:
    key = _name_key(name)
    if key:
        used_names.add(key)


def _apply_candidate(activity: Dict[str, Any], candidate: Dict[str, Any], category: str) -> Dict[str, Any]:
    name = str(candidate.get("name", "") or "").strip()
    next_activity = dict(activity)
    old_location = str(next_activity.get("location", "") or "").strip()
    if name:
        next_activity["location"] = name
        current_title = str(next_activity.get("title") or "").strip()
        if (
            category != "food"
            and (
                not current_title
                or _looks_like_place_phrase(current_title)
                or _looks_like_transport_title(current_title)
                or _name_match_score(current_title, name) < 45
            )
        ):
            next_activity["title"] = name
        elif not current_title:
            next_activity["title"] = name
    next_activity["source"] = candidate.get("source", next_activity.get("source", ""))
    next_activity["source_id"] = candidate.get("id", next_activity.get("source_id", ""))
    next_activity["score"] = candidate.get("score", next_activity.get("score"))
    if candidate.get("opening_hours"):
        next_activity["opening_hours"] = candidate.get("opening_hours")
    if category == "food":
        next_activity["type"] = "美食餐饮"
        next_activity["ticket_price"] = 0
        if candidate.get("price"):
            next_activity["cost_estimate"] = _safe_int(candidate.get("price"), next_activity.get("cost_estimate", 80))
    lat = _safe_float(candidate.get("lat"))
    lng = _safe_float(candidate.get("lng"))
    if lat and lng:
        next_activity["coordinates"] = {"lat": lat, "lng": lng}
        next_activity["lat"] = lat
        next_activity["lng"] = lng
    description = str(candidate.get("description", "") or "").strip()
    address = str(candidate.get("address", "") or "").strip()
    opening_hours = str(candidate.get("opening_hours", "") or "").strip()
    details = [part for part in (description, address, opening_hours) if part]
    if details:
        current_description = str(next_activity.get("description", "") or "").strip()
        next_activity["description"] = current_description if name and name in current_description else "；".join(details[:3])
    if candidate.get("image_url") and not next_activity.get("image"):
        next_activity["image"] = candidate.get("image_url")
    return next_activity


def _looks_like_place_phrase(value: Any) -> bool:
    text = str(value or "")
    return any(word in text for word in ACTIVITY_WORDS)


def _replace_route_outliers(
    activities: List[Dict[str, Any]],
    pools: Dict[str, List[Dict[str, Any]]],
    used_names: set[str],
    center: tuple[float, float] | None,
    day_index: int,
    patch_actions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not center:
        return activities
    repaired: List[Dict[str, Any]] = []
    for activity in activities:
        coord = _activity_coord(activity)
        if not coord or _distance_km(center, coord) <= OUTLIER_DISTANCE_KM:
            repaired.append(activity)
            continue
        category = _activity_category(activity)
        replacement = _pick_replacement_candidate(pools, category, used_names, center)
        if replacement:
            patch_actions.append(
                {
                    "day": day_index + 1,
                    "action": "replace_route_outlier",
                    "from": activity.get("location", ""),
                    "to": replacement.get("name", ""),
                    "distance_km": round(_distance_km(center, coord), 1),
                }
            )
            activity = _apply_candidate(activity, replacement, category)
            _mark_name_used(used_names, replacement.get("name", ""))
        repaired.append(activity)
    return repaired


def _repair_dinner_near_hotel(
    activities: List[Dict[str, Any]],
    pools: Dict[str, List[Dict[str, Any]]],
    used_names: set[str],
    hotel_coord: tuple[float, float] | None,
    day_index: int,
    patch_actions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not hotel_coord:
        return activities
    food_indexes = _food_indexes(activities)
    if not food_indexes:
        return activities

    dinner_index = food_indexes[-1]
    dinner = activities[dinner_index]
    dinner_coord = _activity_coord(dinner)
    if not dinner_coord or _distance_km(dinner_coord, hotel_coord) <= DINNER_HOTEL_MAX_KM:
        return activities

    replacement = _pick_replacement_candidate(pools, "food", used_names, hotel_coord)
    replacement_coord = _candidate_coord(replacement or {})
    if not replacement or not replacement_coord:
        return activities
    if _distance_km(replacement_coord, hotel_coord) >= _distance_km(dinner_coord, hotel_coord):
        return activities

    repaired = list(activities)
    repaired[dinner_index] = _apply_candidate(dinner, replacement, "food")
    _mark_name_used(used_names, replacement.get("name", ""))
    patch_actions.append(
        {
            "day": day_index + 1,
            "action": "replace_dinner_near_hotel",
            "from": dinner.get("location", ""),
            "to": replacement.get("name", ""),
            "distance_km": round(_distance_km(dinner_coord, hotel_coord), 1),
        }
    )
    return repaired


def _repair_meals_near_route(
    activities: List[Dict[str, Any]],
    pools: Dict[str, List[Dict[str, Any]]],
    used_names: set[str],
    hotel_coord: tuple[float, float] | None,
    day_index: int,
    patch_actions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    repaired = list(activities)
    food_indexes = _food_indexes(repaired)
    if not food_indexes:
        return repaired

    for position, index in enumerate(food_indexes):
        if index >= len(repaired):
            continue
        meal = repaired[index]
        meal_coord = _activity_coord(meal)
        anchor = _meal_anchor(repaired, index, position == len(food_indexes) - 1, hotel_coord)
        if not anchor or not meal_coord or _distance_km(meal_coord, anchor) <= MEAL_ROUTE_MAX_KM:
            continue

        replacement = _pick_replacement_candidate(pools, "food", used_names, anchor)
        replacement_coord = _candidate_coord(replacement or {})
        if not replacement or not replacement_coord:
            continue
        if _distance_km(replacement_coord, anchor) >= _distance_km(meal_coord, anchor):
            continue

        repaired[index] = _apply_candidate(meal, replacement, "food")
        _mark_name_used(used_names, replacement.get("name", ""))
        patch_actions.append(
            {
                "day": day_index + 1,
                "action": "replace_meal_near_route",
                "from": meal.get("location", ""),
                "to": replacement.get("name", ""),
                "distance_km": round(_distance_km(meal_coord, anchor), 1),
            }
        )
    return repaired


def _repair_closing_near_hotel(
    activities: List[Dict[str, Any]],
    pools: Dict[str, List[Dict[str, Any]]],
    used_names: set[str],
    hotel_coord: tuple[float, float] | None,
    day_index: int,
    patch_actions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not hotel_coord or not activities:
        return activities
    closing = activities[-1]
    closing_coord = _activity_coord(closing)
    if not closing_coord or _distance_km(closing_coord, hotel_coord) <= CLOSING_HOTEL_MAX_KM:
        return activities

    category = _activity_category(closing)
    replacement = _pick_replacement_candidate(pools, category, used_names, hotel_coord)
    replacement_coord = _candidate_coord(replacement or {})
    if not replacement or not replacement_coord:
        return activities
    if _distance_km(replacement_coord, hotel_coord) >= _distance_km(closing_coord, hotel_coord):
        return activities

    repaired = list(activities)
    repaired[-1] = _apply_candidate(closing, replacement, category)
    _mark_name_used(used_names, replacement.get("name", ""))
    patch_actions.append(
        {
            "day": day_index + 1,
            "action": "replace_closing_near_hotel",
            "from": closing.get("location", ""),
            "to": replacement.get("name", ""),
            "distance_km": round(_distance_km(closing_coord, hotel_coord), 1),
        }
    )
    return repaired


def _meal_anchor(
    activities: Sequence[Dict[str, Any]],
    index: int,
    is_last_meal: bool,
    hotel_coord: tuple[float, float] | None,
) -> tuple[float, float] | None:
    prev_coord = _nearest_activity_coord(activities, index, -1)
    next_coord = _nearest_activity_coord(activities, index, 1)
    if is_last_meal:
        return hotel_coord or prev_coord or next_coord
    if prev_coord and next_coord:
        return ((prev_coord[0] + next_coord[0]) / 2, (prev_coord[1] + next_coord[1]) / 2)
    return prev_coord or next_coord or hotel_coord


def _nearest_activity_coord(
    activities: Sequence[Dict[str, Any]],
    start_index: int,
    direction: int,
) -> tuple[float, float] | None:
    index = start_index + direction
    while 0 <= index < len(activities):
        activity = activities[index]
        if _activity_category(activity) != "food":
            coord = _activity_coord(activity)
            if coord:
                return coord
        index += direction
    return None


def _pick_replacement_candidate(
    pools: Dict[str, List[Dict[str, Any]]],
    category: str,
    used_names: Iterable[str],
    center: tuple[float, float] | None,
) -> Dict[str, Any] | None:
    used = set(used_names)
    candidates = [item for item in pools.get(category, []) if not _is_name_used(used, item.get("name", ""))]
    if not candidates:
        candidates = list(pools.get(category, []) or [])
    if not candidates:
        return None
    if not center:
        return dict(candidates[0])
    with_distance = []
    for item in candidates:
        coord = _candidate_coord(item)
        if not coord:
            continue
        with_distance.append((_distance_km(center, coord), float(item.get("score", 0) or 0), item))
    if not with_distance:
        return dict(candidates[0])
    with_distance.sort(key=lambda value: (value[0], -value[1]))
    return dict(with_distance[0][2])


def _pick_hotel_near_anchor(
    pools: Dict[str, List[Dict[str, Any]]],
    anchor: tuple[float, float] | None,
) -> Dict[str, Any] | None:
    hotels = list(pools.get("hotel", []) or [])
    if not hotels:
        return None
    if not anchor:
        return dict(hotels[0])
    ranked = []
    for hotel in hotels:
        coord = _candidate_coord(hotel)
        if not coord:
            continue
        ranked.append((_distance_km(anchor, coord), -float(hotel.get("score", 0) or 0), hotel))
    if not ranked:
        return dict(hotels[0])
    ranked.sort(key=lambda item: (item[0], item[1]))
    return dict(ranked[0][2])


def _should_anchor_hotel_to_day_area(
    hotel_coord: tuple[float, float] | None,
    activity_center: tuple[float, float] | None,
) -> bool:
    if not activity_center:
        return False
    if not hotel_coord:
        return True
    return _distance_km(hotel_coord, activity_center) > CLOSING_HOTEL_MAX_KM


def _best_day_center(activities: Sequence[Dict[str, Any]], hotel_coord: tuple[float, float] | None = None) -> tuple[float, float] | None:
    coords = [coord for coord in (_activity_coord(item) for item in activities) if coord]
    if hotel_coord:
        coords.append(hotel_coord)
    if not coords:
        return None
    best = min(coords, key=lambda coord: sum(_distance_km(coord, other) for other in coords))
    return best


def _fallback_day_center(pools: Dict[str, List[Dict[str, Any]]], day_index: int) -> tuple[float, float] | None:
    attractions = [item for item in pools.get("attraction", []) if _candidate_coord(item)]
    if not attractions:
        return None
    index = min(day_index * 2, len(attractions) - 1)
    return _candidate_coord(attractions[index])


def _order_day_route(activities: List[Dict[str, Any]], hotel_coord: tuple[float, float] | None = None) -> List[Dict[str, Any]]:
    if len(activities) < 3:
        return activities
    original_total = _route_metrics(activities, hotel_coord)["total_distance_km"]
    remaining = list(activities)
    ordered = [remaining.pop(0)]
    while remaining:
        current = _activity_coord(ordered[-1])
        if not current:
            ordered.append(remaining.pop(0))
            continue
        next_index = min(
            range(len(remaining)),
            key=lambda index: _route_order_score(current, _activity_coord(remaining[index]) or current, hotel_coord, remaining[index]),
        )
        ordered.append(remaining.pop(next_index))
    ordered_total = _route_metrics(ordered, hotel_coord)["total_distance_km"]
    return ordered if ordered_total < original_total else activities


def _route_order_score(
    current: tuple[float, float],
    candidate: tuple[float, float],
    hotel_coord: tuple[float, float] | None,
    activity: Dict[str, Any],
) -> float:
    score = _distance_km(current, candidate)
    if hotel_coord:
        hotel_distance = _distance_km(candidate, hotel_coord)
        score += hotel_distance * (0.2 if _activity_category(activity) == "food" else 0.1)
    return score


def _arrange_dinner_towards_hotel(
    activities: List[Dict[str, Any]],
    hotel_coord: tuple[float, float] | None,
) -> List[Dict[str, Any]]:
    if not hotel_coord:
        return activities
    food_indexes = _food_indexes(activities)
    if len(food_indexes) < 2:
        return activities

    dinner_index = min(
        food_indexes,
        key=lambda index: _distance_km(_activity_coord(activities[index]) or hotel_coord, hotel_coord),
    )
    if dinner_index == len(activities) - 1:
        return activities
    ordered = [item for index, item in enumerate(activities) if index != dinner_index]
    ordered.append(activities[dinner_index])
    return ordered


def _repair_time_incompatible_activities(
    activities: List[Dict[str, Any]],
    pools: Dict[str, List[Dict[str, Any]]],
    used_names: set[str],
    day_index: int,
    patch_actions: List[Dict[str, Any]],
    *,
    start_after_minutes: int | None = None,
    end_before_minutes: int | None = None,
) -> List[Dict[str, Any]]:
    cursor = max(9 * 60 + 30, start_after_minutes or 0)
    food_indexes = _food_indexes(activities)
    has_evening = _has_evening_activity(activities)
    used_meals: set[str] = set()
    repaired: List[Dict[str, Any]] = []

    for index, activity in enumerate(activities):
        next_activity = dict(activity)
        category = _activity_category(next_activity)
        if category == "food":
            meal_kind = _scheduled_meal_kind(index, food_indexes, next_activity)
            if meal_kind in used_meals:
                if meal_kind != "dinner" and "tea" not in used_meals and cursor < 17 * 60:
                    meal_kind = "tea"
                else:
                    continue
            start = _meal_start_minutes(meal_kind, cursor, has_evening)
            duration = _meal_duration_minutes(meal_kind)
        else:
            duration = max(min(_safe_int(next_activity.get("duration"), 90), 120), 60)
            start = _activity_start_minutes(next_activity, cursor)

        if _next_available_activity_start(next_activity, start, duration, end_before_minutes) is None:
            replacement = _pick_time_fit_replacement(
                pools,
                category,
                used_names,
                next_activity,
                start,
                duration,
                end_before_minutes,
            )
            if not replacement:
                patch_actions.append(
                    {
                        "day": day_index + 1,
                        "action": "remove_time_incompatible_activity",
                        "from": _activity_place_text(next_activity),
                    }
                )
                continue
            original = _activity_place_text(next_activity)
            next_activity = _apply_candidate(next_activity, replacement, category)
            _mark_name_used(used_names, replacement.get("name", ""))
            patch_actions.append(
                {
                    "day": day_index + 1,
                    "action": "replace_time_incompatible_activity",
                    "from": original,
                    "to": replacement.get("name", ""),
                }
            )

        repaired.append(next_activity)
        cursor = start + duration + 20
        if category == "food":
            used_meals.add(meal_kind)
    return repaired


def _pick_time_fit_replacement(
    pools: Dict[str, List[Dict[str, Any]]],
    category: str,
    used_names: Iterable[str],
    activity: Dict[str, Any],
    start: int,
    duration: int,
    end_before_minutes: int | None,
) -> Dict[str, Any] | None:
    used = set(used_names)
    source_coord = _activity_coord(activity)
    candidates = []
    for item in pools.get(category, []) or []:
        name = str(item.get("name", "") or "").strip()
        if not name or _is_name_used(used, name):
            continue
        probe = {
            "title": name,
            "location": name,
            "description": item.get("description", ""),
            "opening_hours": item.get("opening_hours", ""),
        }
        if _next_available_activity_start(probe, start, duration, end_before_minutes) is None:
            continue
        coord = _candidate_coord(item)
        distance = _distance_km(source_coord, coord) if source_coord and coord else 0.0
        candidates.append((distance, -float(item.get("score", 0) or 0), item))
    if not candidates:
        return None
    candidates.sort(key=lambda value: (value[0], value[1]))
    return dict(candidates[0][2])


def _has_evening_activity(activities: Sequence[Dict[str, Any]]) -> bool:
    return any(_is_evening_activity(activity) for activity in activities if _activity_category(activity) != "food")


def _is_evening_activity(activity: Dict[str, Any]) -> bool:
    hour = _start_hour(activity.get("time"))
    if hour is not None and hour >= 18:
        return not _is_daytime_only_activity(activity)
    text = _activity_text(activity)
    return any(token in text for token in EVENING_ACTIVITY_TOKENS)


def _append_return_terminal(
    activities: List[Dict[str, Any]],
    return_terminal: Dict[str, Any],
) -> List[Dict[str, Any]]:
    terminal = dict(return_terminal)
    terminal.setdefault("type", "交通衔接")
    terminal.setdefault("duration", 90)
    terminal["is_terminal_transport"] = True

    terminal_hour = _start_hour(terminal.get("time"))
    if terminal_hour is None:
        previous_end = _end_minutes(activities[-1].get("time")) if activities else None
        start = max(previous_end + 30 if previous_end is not None else 15 * 60, 15 * 60)
        terminal["time"] = _format_time_range(start, max(_safe_int(terminal.get("duration"), 90), 60))

    return [*activities, terminal]


def _assign_route_times(
    activities: List[Dict[str, Any]],
    *,
    start_after_minutes: int | None = None,
    end_before_minutes: int | None = None,
) -> List[Dict[str, Any]]:
    food_indexes = _food_indexes(activities)
    has_evening = _has_evening_activity(activities)
    cursor = max(9 * 60 + 30, start_after_minutes or 0)
    used_meals: set[str] = set()
    result: List[Dict[str, Any]] = []
    for index, activity in enumerate(activities):
        if len(result) >= 6:
            break
        next_activity = dict(activity)
        if _activity_category(next_activity) == "food":
            meal_kind = _scheduled_meal_kind(index, food_indexes, next_activity)
            if meal_kind in used_meals:
                if meal_kind != "dinner" and "tea" not in used_meals and cursor < 17 * 60:
                    meal_kind = "tea"
                else:
                    continue
            start = _meal_start_minutes(meal_kind, cursor, has_evening)
            duration = _meal_duration_minutes(meal_kind)
            next_start = _next_available_activity_start(next_activity, start, duration, end_before_minutes)
            if next_start is None:
                continue
            start = next_start
            if end_before_minutes is not None and start + duration > end_before_minutes:
                continue
            next_activity["time"] = _format_time_range(start, duration)
            cursor = start + duration + 20
            used_meals.add(meal_kind)
            next_activity = _normalize_meal_activity(next_activity, meal_kind)
        else:
            duration = max(min(_safe_int(next_activity.get("duration"), 90), 120), 60)
            start = _activity_start_minutes(next_activity, cursor)
            next_start = _next_available_activity_start(next_activity, start, duration, end_before_minutes)
            if next_start is None:
                continue
            start = next_start
            if end_before_minutes is not None and start + duration > end_before_minutes:
                continue
            next_activity["time"] = _format_time_range(start, duration)
            cursor = start + duration + 20
        result.append(next_activity)
    return sorted(result, key=lambda item: _time_sort_key(item.get("time")))


def _meal_start_minutes(meal_kind: str, cursor: int, has_evening: bool) -> int:
    if meal_kind == "breakfast":
        return max(cursor, 8 * 60)
    if meal_kind == "lunch":
        return max(cursor, 12 * 60)
    if meal_kind == "tea":
        return max(cursor, 15 * 60 + 20)
    dinner_floor = 17 * 60 + 30 if has_evening else 17 * 60 + 50
    return min(max(cursor, dinner_floor), 19 * 60 + 10)


def _meal_duration_minutes(meal_kind: str) -> int:
    if meal_kind == "tea":
        return 50
    if meal_kind == "breakfast":
        return 60
    return 80


def _activity_start_minutes(activity: Dict[str, Any], cursor: int) -> int:
    explicit_hour = _start_hour(activity.get("time"))
    if explicit_hour is not None and explicit_hour >= 18:
        return max(int(explicit_hour * 60), cursor)
    if _is_evening_activity(activity):
        return max(cursor, 19 * 60 + 30)
    if 11 * 60 + 30 <= cursor < 13 * 60 + 40:
        return 14 * 60
    if 17 * 60 + 20 <= cursor < 19 * 60 + 20:
        return 19 * 60 + 30
    return cursor


def _next_available_activity_start(
    activity: Dict[str, Any],
    preferred_start: int,
    duration: int,
    end_before_minutes: int | None = None,
) -> int | None:
    latest_end = end_before_minutes if end_before_minutes is not None else 24 * 60
    ranges = _opening_ranges_minutes(activity)
    if ranges:
        for open_at, close_at in ranges:
            start = max(preferred_start, open_at)
            if start + duration <= min(close_at, latest_end):
                return start
        return None

    if _is_daytime_only_activity(activity) and preferred_start >= 18 * 60:
        return None
    return preferred_start if preferred_start + duration <= latest_end else None


def _opening_ranges_minutes(activity: Dict[str, Any]) -> List[tuple[int, int]]:
    text = " ".join(
        str(activity.get(key, "") or "")
        for key in ("opening_hours", "open_time", "business_hours", "description", "tips")
    )
    if not text:
        return []
    if any(token in text for token in ("全天", "24小时", "00:00-24:00", "00:00–24:00")):
        return [(0, 24 * 60)]

    ranges: List[tuple[int, int]] = []
    pattern = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*(?:-|~|–|—|至|到)\s*(\d{1,2})(?::(\d{2}))?")
    for match in pattern.finditer(text):
        start = int(match.group(1)) * 60 + int(match.group(2) or 0)
        end = int(match.group(3)) * 60 + int(match.group(4) or 0)
        if end <= start:
            end += 24 * 60
        if end - start >= 30:
            ranges.append((start, min(end, 24 * 60)))
    return ranges


def _is_daytime_only_activity(activity: Dict[str, Any]) -> bool:
    text = _activity_text(activity)
    if any(token in text for token in NIGHT_SAFE_TOKENS):
        return False
    return any(token in text for token in DAYTIME_POI_TOKENS)


def _format_time_range(start_minutes: int, duration_minutes: int) -> str:
    start_minutes = max(0, min(start_minutes, 23 * 60))
    end_minutes = max(start_minutes + 30, min(start_minutes + duration_minutes, 23 * 60 + 30))
    return f"{_format_clock(start_minutes)}-{_format_clock(end_minutes)}"


def _format_clock(total_minutes: int) -> str:
    hours = max(0, total_minutes // 60)
    minutes = max(0, total_minutes % 60)
    return f"{hours:02d}:{minutes:02d}"


def _format_duration(minutes: int) -> str:
    if minutes <= 0:
        return "待估算"
    hours = minutes // 60
    remain = minutes % 60
    if hours and remain:
        return f"{hours}小时{remain}分钟"
    if hours:
        return f"{hours}小时"
    return f"{remain}分钟"


def _scheduled_meal_kind(index: int, food_indexes: Sequence[int], activity: Dict[str, Any]) -> str:
    position = list(food_indexes).index(index) if index in food_indexes else 0
    explicit = _explicit_meal_kind(activity)
    if len(food_indexes) == 1:
        if explicit in {"breakfast", "tea", "dinner"}:
            return explicit
        return "dinner" if index >= 3 else "lunch"
    if explicit == "breakfast" and position == 0:
        return "breakfast"
    if position == len(food_indexes) - 1:
        return "dinner"
    if len(food_indexes) >= 3 and position == len(food_indexes) - 2:
        return "tea"
    return "lunch"


def _explicit_meal_kind(activity: Dict[str, Any]) -> str:
    text = " ".join(
        str(activity.get(key, "") or "")
        for key in ("title", "type", "description", "location")
    )
    if "早餐" in text or "早茶" in text or "早午茶" in text:
        return "breakfast"
    if "下午茶" in text or "茶歇" in text:
        return "tea"
    if "晚餐" in text or "晚饭" in text or "夜宵" in text:
        return "dinner"
    if "午餐" in text or "午饭" in text:
        return "lunch"
    start_hour = _start_hour(activity.get("time"))
    if start_hour is not None:
        if start_hour < 10:
            return "breakfast"
        if start_hour < 14:
            return "lunch"
        if start_hour < 17:
            return "tea"
        return "dinner"
    return ""


def _normalize_meal_activity(activity: Dict[str, Any], meal_kind: str) -> Dict[str, Any]:
    labels = {
        "breakfast": "早餐",
        "lunch": "午餐",
        "tea": "下午茶",
        "dinner": "晚餐",
    }
    label = labels.get(meal_kind, "用餐")
    next_activity = dict(activity)
    location = str(next_activity.get("location") or "").strip()
    title = str(next_activity.get("title") or location or label).strip()
    title = re.sub(r"^(早餐|早茶|早午茶|午餐|午饭|下午茶|晚餐|晚饭|夜宵)[：:\s-]*", "", title).strip()
    if _looks_like_transport_title(title):
        title = location
    if not title or title == location:
        title = location or "餐饮安排"
    next_activity["title"] = f"{label}：{title}"
    next_activity["type"] = "美食餐饮"
    next_activity["ticket_price"] = 0
    return next_activity


def _looks_like_transport_title(value: Any) -> bool:
    text = str(value or "")
    return any(token in text for token in TRANSPORT_TITLE_TOKENS)


def _next_available_time(times: Sequence[str], start_index: int, used_starts: set[str]) -> str:
    for offset in range(len(times)):
        candidate = times[min(start_index + offset, len(times) - 1)]
        if _start_time(candidate) not in used_starts:
            return candidate
    return times[-1]


def _start_time(value: Any) -> str:
    return str(value or "").split("-", 1)[0].strip()


def _start_hour(value: Any) -> float | None:
    matched = re.search(r"(\d{1,2})(?::(\d{2}))?", str(value or ""))
    if not matched:
        return None
    hour = int(matched.group(1))
    minute = int(matched.group(2) or 0)
    return hour + minute / 60


def _end_minutes(value: Any) -> int | None:
    text = str(value or "")
    parts = text.split("-", 1)
    if len(parts) < 2:
        hour = _start_hour(text)
        return int(hour * 60) if hour is not None else None
    hour = _start_hour(parts[1])
    return int(hour * 60) if hour is not None else None


def _time_sort_key(value: Any) -> float:
    hour = _start_hour(value)
    return hour if hour is not None else 24.0


def _route_metrics(activities: Sequence[Dict[str, Any]], hotel_coord: tuple[float, float] | None = None) -> Dict[str, Any]:
    coords = [coord for coord in (_activity_coord(item) for item in activities) if coord]
    legs = [_distance_km(coords[index], coords[index + 1]) for index in range(len(coords) - 1)]
    total = sum(legs)
    max_leg = max(legs) if legs else 0.0
    closing_to_hotel = _distance_km(coords[-1], hotel_coord) if coords and hotel_coord else 0.0
    warnings: List[str] = []
    if max_leg > MAX_REASONABLE_LEG_KM:
        warnings.append("当天存在过长单段移动")
    if total > MAX_REASONABLE_DAY_KM:
        warnings.append("当天总移动距离偏长")
    if closing_to_hotel > CLOSING_HOTEL_MAX_KM:
        warnings.append("最后一站距离当天酒店偏远")
    return {
        "point_count": len(coords),
        "total_distance_km": round(total, 1),
        "max_leg_km": round(max_leg, 1),
        "closing_to_hotel_km": round(closing_to_hotel, 1),
        "warnings": warnings,
    }


def _food_indexes(activities: Sequence[Dict[str, Any]]) -> List[int]:
    return [index for index, activity in enumerate(activities) if _activity_category(activity) == "food"]


def _activity_place_text(activity: Dict[str, Any]) -> str:
    return str(activity.get("location") or activity.get("title") or "").strip()


def _activity_coord(activity: Dict[str, Any]) -> tuple[float, float] | None:
    coordinates = activity.get("coordinates") or {}
    lat = _safe_float(coordinates.get("lat") or activity.get("lat"))
    lng = _safe_float(coordinates.get("lng") or activity.get("lng"))
    return (lat, lng) if lat and lng else None


def _hotel_coord(hotel: Dict[str, Any]) -> tuple[float, float] | None:
    coordinates = hotel.get("coordinates") or {}
    lat = _safe_float(coordinates.get("lat") or hotel.get("lat"))
    lng = _safe_float(coordinates.get("lng") or hotel.get("lng"))
    return (lat, lng) if lat and lng else None


def _candidate_coord(candidate: Dict[str, Any]) -> tuple[float, float] | None:
    lat = _safe_float(candidate.get("lat"))
    lng = _safe_float(candidate.get("lng"))
    return (lat, lng) if lat and lng else None


def _distance_km(left: tuple[float, float], right: tuple[float, float]) -> float:
    lat1, lng1 = left
    lat2, lng2 = right
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        matched = re.search(r"\d+(?:\.\d+)?", str(value or ""))
        return int(float(matched.group())) if matched else default
    except Exception:
        return default
