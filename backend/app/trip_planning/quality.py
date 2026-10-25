"""Deterministic checks for a generated itinerary.

The score is a coverage indicator, not a claim that opening hours, prices or
availability were checked in real time.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List

from app.trip_planning.utils import compact_name

MAP_SOURCES = {"geo", "amap", "amap_mcp", "amap_mcp_sse", "tencent"}
MEAL_TOKENS = ("美食", "餐饮", "早餐", "午餐", "晚餐", "小吃")
TRANSPORT_TOKENS = ("交通", "高铁", "动车", "航班", "飞机", "公交", "地铁", "打车")
TIME_RANGE = re.compile(r"^(\d{1,2}):(\d{2})\s*[-–—~至]\s*(\d{1,2}):(\d{2})$")


def audit_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    plan = list(state.get("plan") or [])
    expected_days = max(int(state.get("days") or len(plan) or 1), 1)
    city = str(state.get("city") or "")
    attraction_ids = _candidate_ids(state.get("attraction_candidates"))
    food_ids = _candidate_ids(state.get("food_candidates"))
    hotel_ids = _candidate_ids(state.get("hotel_options"))

    poi_count = verified_count = attraction_count = verified_attraction_count = meal_days = occupied_days = 0
    verified_hotel_nights = 0
    route_days = routed_days = 0
    time_conflicts = 0
    location_keys: List[str] = []
    unverified_names: List[str] = []

    for index, day in enumerate(plan):
        activities = [item for item in day.get("activities") or [] if isinstance(item, dict)]
        places = [item for item in activities if not _is_transport(item) and not _is_lodging(item)]
        if any(not _is_meal(item) for item in places):
            occupied_days += 1
        if any(_is_meal(item) for item in places):
            meal_days += 1
        time_conflicts += _time_conflicts(activities)

        for activity in places:
            poi_count += 1
            if not _is_meal(activity):
                attraction_count += 1
            source_id = str(activity.get("source_id") or "").strip()
            expected_ids = food_ids if _is_meal(activity) else attraction_ids
            verified = (
                str(activity.get("source") or "").lower() in MAP_SOURCES
                and bool(source_id and source_id in expected_ids)
                and _has_coordinates(activity)
            )
            if verified:
                verified_count += 1
                if not _is_meal(activity):
                    verified_attraction_count += 1
            else:
                unverified_names.append(str(activity.get("location") or activity.get("title") or "未命名地点"))
            key = source_id if verified else compact_name(str(activity.get("location") or activity.get("title") or ""), city)
            if key:
                location_keys.append(key)

        if index < expected_days - 1:
            hotel = day.get("hotel_recommendation") or {}
            if (
                str(hotel.get("source") or "").lower() in MAP_SOURCES
                and str(hotel.get("source_id") or "") in hotel_ids
                and _has_coordinates(hotel)
            ):
                verified_hotel_nights += 1

        routed_places = [item for item in activities if _has_coordinates(item) and not _is_transport(item)]
        if len(routed_places) >= 2:
            route_days += 1
            route = day.get("map_route") or {}
            if len(route.get("legs") or []) == len(routed_places) - 1 and not route.get("partial") and all(leg.get("ok") for leg in route["legs"]):
                routed_days += 1

    duplicate_count = len(location_keys) - len(set(location_keys))
    expected_nights = max(expected_days - 1, 0)
    budget = state.get("estimated_budget") or {}
    daily_budgets = state.get("daily_budgets") or []
    budget_consistent = bool(budget) and (
        int(budget.get("total") or 0) == sum(int(value or 0) for value in (budget.get("breakdown") or {}).values())
        and (not daily_budgets or int(budget.get("total") or 0) == sum(int(day.get("total") or 0) for day in daily_budgets))
    )

    issues: List[str] = []
    if occupied_days < expected_days:
        issues.append(f"有 {expected_days - occupied_days} 天缺少可游览地点，请补充或调整行程。")
    if unverified_names:
        sample = "、".join(dict.fromkeys(unverified_names[:3]))
        issues.append(f"有 {len(unverified_names)} 个活动未能与地图候选准确匹配（如 {sample}），出发前请核对。")
    if meal_days < expected_days:
        issues.append(f"有 {expected_days - meal_days} 天未安排餐饮，请按实际需求补充。")
    if verified_hotel_nights < expected_nights:
        issues.append("部分住宿尚未核验到具体酒店，请确认可预订的酒店与房价。")
    if routed_days < route_days:
        issues.append("部分每日路段未取得完整路线，请在地图中核对交通方式和耗时。")
    if duplicate_count:
        issues.append(f"有 {duplicate_count} 个地点重复安排，请检查是否符合预期。")
    if time_conflicts:
        issues.append(f"有 {time_conflicts} 处活动时间重叠，请调整当天安排。")
    if not budget_consistent:
        issues.append("预算总额与分类或每日金额未能核对一致，请重新检查费用。")

    coverage = {
        "verified_location_ratio": _ratio(verified_count, poi_count) if poi_count else 0.0,
        "day_coverage_ratio": _ratio(occupied_days, expected_days),
        "meal_coverage_ratio": _ratio(meal_days, expected_days),
        "hotel_coverage_ratio": _ratio(verified_hotel_nights, expected_nights),
        "route_coverage_ratio": _ratio(routed_days, route_days),
        "unique_location_ratio": _ratio(len(set(location_keys)), len(location_keys)) if location_keys else 0.0,
    }
    score = round(
        coverage["verified_location_ratio"] * 40
        + coverage["day_coverage_ratio"] * 20
        + coverage["meal_coverage_ratio"] * 10
        + coverage["hotel_coverage_ratio"] * 10
        + coverage["route_coverage_ratio"] * 10
        + coverage["unique_location_ratio"] * 10
        - min(time_conflicts * 5, 10)
        - (0 if budget_consistent else 10),
        1,
    )
    return {
        "score": max(0.0, min(score, 100.0)),
        **coverage,
        "verified_poi_count": verified_count,
        "poi_count": poi_count,
        "verified_attraction_count": verified_attraction_count,
        "attraction_count": attraction_count,
        "review": "已通过基本结构和地图来源检查。" if not issues else "发现需要出行前核对的项目。",
        "issues": issues,
    }


def _candidate_ids(items: Any) -> set[str]:
    return {str(item.get("id") or "").strip() for item in (items or []) if isinstance(item, dict) and item.get("id")}


def _is_meal(activity: Dict[str, Any]) -> bool:
    kind = str(activity.get("type") or "")
    if any(token in kind for token in MEAL_TOKENS):
        return True
    if any(token in kind for token in ("景点", "游览", "文化", "户外", "交通")):
        return False
    return any(token in str(activity.get("title") or "") for token in MEAL_TOKENS)


def _is_transport(activity: Dict[str, Any]) -> bool:
    if activity.get("is_intercity_transport") or activity.get("isIntercityTransport"):
        return True
    kind = str(activity.get("type") or "")
    if any(token in kind for token in TRANSPORT_TOKENS):
        return True
    if kind and kind not in ("其他", "other"):
        return False
    return any(token in str(activity.get("title") or "") for token in TRANSPORT_TOKENS) and not _is_meal(activity)


def _is_lodging(activity: Dict[str, Any]) -> bool:
    kind = str(activity.get("type") or "")
    title = str(activity.get("title") or "")
    return "住宿" in kind or any(token in title for token in ("办理入住", "返回酒店", "酒店休息", "回酒店"))


def _has_coordinates(item: Dict[str, Any]) -> bool:
    coords = item.get("coordinates") or {}
    try:
        lat = float(coords.get("lat", item.get("lat")))
        lng = float(coords.get("lng", item.get("lng")))
    except (TypeError, ValueError):
        return False
    return math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180 and bool(lat and lng)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 2) if denominator else 1.0


def _time_conflicts(activities: List[Dict[str, Any]]) -> int:
    intervals = []
    for activity in activities:
        match = TIME_RANGE.match(str(activity.get("time") or "").strip())
        if not match:
            continue
        start_hour, start_minute, end_hour, end_minute = map(int, match.groups())
        if max(start_hour, end_hour) > 23 or max(start_minute, end_minute) > 59:
            continue
        start = start_hour * 60 + start_minute
        end = end_hour * 60 + end_minute
        if end > start:
            intervals.append((start, end))
    intervals.sort()
    return sum(start < previous_end for (_, previous_end), (start, _) in zip(intervals, intervals[1:]))
