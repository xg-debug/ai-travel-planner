import math
import re
from typing import Any, Dict, List

from app.agents.schemas import ReflectionContextModel, ReflectionHistoryEntryModel, ReviewIssueModel
from app.agents.shared import normalize_itinerary
from app.orchestration.task_models import build_task_result
from app.orchestration.task_router import complete_task, reset_task_chain, task_can_retry

DINNER_HOTEL_MAX_KM = 10.0
CLOSING_HOTEL_MAX_KM = 18.0
HOTEL_ACTIVITY_TOKENS = ("入住", "办理入住", "酒店休息", "返回酒店", "回酒店", "住宿", "check-in", "check in")
TRANSPORT_TITLE_TOKENS = ("前往", "驱车", "打车", "乘车", "坐车", "自驾", "抵达", "出发", "返程", "返回", "上岛", "离岛", "交通", "路线")
RETURN_TERMINAL_TOKENS = ("返程", "返回", "回程", "离开", "回到出发地", "返回出发地", "返抵", "返家")
RETURN_TRANSPORT_TOKENS = ("高铁", "动车", "火车", "飞机", "航班", "机场", "车站", "大巴", "客运", "铁路", "交通")
INTERCITY_ACTIVITY_TOKENS = ("城际交通", "大交通", "往返交通", "去程交通", "返程交通")
DAYTIME_POI_TOKENS = ("博物馆", "纪念馆", "展览馆", "展馆", "美术馆", "科技馆", "文化馆", "图书馆", "故居", "会馆", "祠堂", "寺", "塔")
NIGHT_SAFE_TOKENS = ("夜景", "夜市", "步行街", "商圈", "酒吧", "演出", "灯光", "广场", "江景", "河景", "散步")
EVENING_ACTIVITY_TOKENS = ("夜", "晚间", "夜景", "夜市", "演出", "灯光", "酒吧", "散步")


def _issue(issue_type: str, severity: str, day: int | None, message: str) -> Dict[str, Any]:
    return ReviewIssueModel(
        type=issue_type,
        severity=severity,
        day=day,
        message=message,
    ).model_dump()


def _review_itinerary(plan: List[Dict[str, Any]], state: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    seen_locations: set[str] = set()
    weather_impacts = list((state or {}).get("weather_impacts", []) or [])
    intercity_transport = (state or {}).get("intercity_transport") or ((state or {}).get("transport_plan") or {}).get("intercity_transport") or {}
    for day in plan:
        day_no = int(day.get("day") or 0) or None
        activities = day.get("activities", []) or []
        if len(activities) < 5:
            issues.append(_issue("missing_activities", "major", day_no, "活动数量不足 5 个"))
        if not day.get("hotel_recommendation"):
            issues.append(_issue("missing_hotel", "major", day_no, "当天缺少酒店推荐"))
        if day_no == 1 and _intercity_leg(intercity_transport, "outbound") and not _has_intercity_direction(activities, "outbound"):
            issues.append(_issue("missing_outbound_transport", "major", day_no, "第一天缺少从出发地到目的地的去程交通安排"))
        if day_no == len(plan) and _intercity_leg(intercity_transport, "inbound") and not _has_intercity_direction(activities, "inbound"):
            issues.append(_issue("missing_inbound_transport", "major", day_no, "最后一天缺少从目的地返回出发地的返程交通安排"))
        if day_no == len(plan):
            after_return = _activities_after_return_terminal(activities)
            if after_return:
                issues.append(
                    _issue(
                        "activity_after_return",
                        "major",
                        day_no,
                        f"返程交通后仍有目的地活动：{'、'.join(after_return[:3])}",
                    )
                )

        food_hits = 0
        day_coords: List[tuple[float, float, str]] = []
        hotel_coord = _day_hotel_coord(day, state or {})
        start_times: set[str] = set()
        dinner_hits = 0
        for activity in activities:
            if _is_synthetic_intercity_transport_activity(activity, intercity_transport):
                issues.append(_issue("duplicate_intercity_activity", "major", day_no, f"存在重复或伪装成普通活动的城际交通：{activity.get('title') or activity.get('location', '')}"))
                continue
            if _is_intercity_transport_activity(activity):
                continue
            text = " ".join(
                [
                    str(activity.get("title", "")),
                    str(activity.get("type", "")),
                    str(activity.get("description", "")),
                    str(activity.get("location", "")),
                ]
            )
            if any(token in text for token in ("早餐", "午餐", "晚餐", "餐", "美食", "小吃")):
                food_hits += 1
            if _classify_activity_category(activity) == "food" and _is_dinner_activity(activity):
                dinner_hits += 1
            if _is_hotel_activity(activity):
                issues.append(_issue("hotel_activity_in_timeline", "minor", day_no, f"入住酒店不应作为普通活动展示：{activity.get('location') or activity.get('title', '')}"))
            start_time = _start_time(activity.get("time"))
            if start_time and start_time in start_times:
                issues.append(_issue("duplicate_start_time", "minor", day_no, f"同一天存在重复开始时间：{start_time}"))
            if start_time:
                start_times.add(start_time)
            meal_conflict = _meal_time_conflict(activity)
            if meal_conflict:
                issues.append(_issue("meal_time_conflict", "minor", day_no, meal_conflict))
            if _activity_closed_at_scheduled_time(activity):
                issues.append(_issue("closed_at_time", "major", day_no, f"活动时间与开放时间不匹配：{activity.get('location') or activity.get('title', '')}"))
            if _title_location_mismatch(activity):
                issues.append(_issue("title_location_mismatch", "minor", day_no, f"标题与地点内容不一致：{activity.get('title', '')} / {activity.get('location', '')}"))
            location = str(activity.get("location", "")).strip()
            location_key = _name_key(location)
            if location_key and location_key in seen_locations:
                issues.append(_issue("duplicate_location", "minor", day_no, f"地点重复：{location}"))
            if location_key:
                seen_locations.add(location_key)
            if not activity.get("source_id") and not activity.get("coordinates"):
                issues.append(_issue("unresolved_poi", "major", day_no, f"活动地点未落地到真实 POI：{location or activity.get('title', '')}"))
            coord = _activity_coord(activity)
            if coord:
                day_coords.append((coord[0], coord[1], location or str(activity.get("title", ""))))

            if day_no and 0 < day_no <= len(weather_impacts):
                impact = weather_impacts[day_no - 1]
                if impact.get("condition_type") in {"rain", "snow", "fog", "hot", "wind"}:
                    if any(token in text for token in ("海", "公园", "山", "户外", "风景", "沙滩", "步道")):
                        issues.append(
                            _issue(
                                "weather_conflict",
                                "minor",
                                day_no,
                                f"天气可能影响户外地点：{location or activity.get('title', '')}",
                            )
                        )

        if food_hits == 0:
            issues.append(_issue("missing_food", "minor", day_no, "当天缺少明确餐饮活动"))
        if dinner_hits > 1:
            issues.append(_issue("duplicate_dinner", "major", day_no, "当天存在多个晚餐安排"))
        issues.extend(_review_route_distance(day_no, day_coords))
        issues.extend(_review_hotel_anchor(day_no, activities, hotel_coord))
    return issues


def _quality_score(plan: List[Dict[str, Any]], issues: List[Dict[str, Any]], state: Dict[str, Any]) -> Dict[str, Any]:
    major = len([issue for issue in issues if issue.get("severity") == "major"])
    minor = len(issues) - major
    total = max(0, 100 - major * 12 - minor * 4)
    route_issues = [issue for issue in issues if str(issue.get("type", "")).startswith("route_") or issue.get("type") == "unresolved_poi"]
    return {
        "total": total,
        "reality": 90 if plan else 0,
        "route": max(45, 82 - len(route_issues) * 12),
        "preference": 82,
        "time": max(60, 90 - major * 10),
        "budget": 76,
        "explainability": 88,
    }


def _activity_coord(activity: Dict[str, Any]) -> tuple[float, float] | None:
    coordinates = activity.get("coordinates") or {}
    try:
        lat = float(coordinates.get("lat") or activity.get("lat") or 0)
        lng = float(coordinates.get("lng") or activity.get("lng") or 0)
        return (lat, lng) if lat and lng else None
    except Exception:
        return None


def _day_hotel_coord(day: Dict[str, Any], state: Dict[str, Any]) -> tuple[float, float] | None:
    hotel = day.get("hotel_recommendation") or day.get("hotel") or {}
    coord = _coord_from_mapping(hotel)
    if coord:
        return coord

    source_id = str(hotel.get("source_id", "") or hotel.get("id", "") or "").strip()
    hotel_name = str(hotel.get("name", "") or "").strip()
    hotel_key = _name_key(hotel_name)
    candidates = list(state.get("scored_hotels") or state.get("hotel_options") or [])
    for candidate in candidates:
        if source_id and str(candidate.get("id", "") or "").strip() == source_id:
            return _coord_from_mapping(candidate)
    for candidate in candidates:
        name_key = _name_key(candidate.get("name", ""))
        if hotel_key and name_key and (hotel_key == name_key or hotel_key in name_key or name_key in hotel_key):
            return _coord_from_mapping(candidate)
    return None


def _coord_from_mapping(item: Dict[str, Any]) -> tuple[float, float] | None:
    coordinates = item.get("coordinates") or {}
    try:
        lat = float(coordinates.get("lat") or item.get("lat") or 0)
        lng = float(coordinates.get("lng") or item.get("lng") or 0)
        return (lat, lng) if lat and lng else None
    except Exception:
        return None


def _review_route_distance(day_no: int | None, coords: List[tuple[float, float, str]]) -> List[Dict[str, Any]]:
    if len(coords) < 2:
        return []
    legs = [
        (_distance_km((coords[index][0], coords[index][1]), (coords[index + 1][0], coords[index + 1][1])), coords[index][2], coords[index + 1][2])
        for index in range(len(coords) - 1)
    ]
    total = sum(item[0] for item in legs)
    max_leg = max(legs, key=lambda item: item[0])
    issues: List[Dict[str, Any]] = []
    if max_leg[0] > 18:
        issues.append(_issue("route_too_long", "major", day_no, f"单段移动过长：{max_leg[1]} 到 {max_leg[2]} 约 {max_leg[0]:.1f}km"))
    if total > 45:
        issues.append(_issue("route_backtracking", "major", day_no, f"当天总移动距离偏长，直线估算约 {total:.1f}km"))
    return issues


def _review_hotel_anchor(
    day_no: int | None,
    activities: List[Dict[str, Any]],
    hotel_coord: tuple[float, float] | None,
) -> List[Dict[str, Any]]:
    if not hotel_coord or not activities:
        return []
    issues: List[Dict[str, Any]] = []
    food_activities = [activity for activity in activities if _classify_activity_category(activity) == "food"]
    if food_activities:
        dinner = food_activities[-1]
        dinner_coord = _activity_coord(dinner)
        if dinner_coord:
            distance = _distance_km(dinner_coord, hotel_coord)
            if distance > DINNER_HOTEL_MAX_KM:
                issues.append(
                    _issue(
                        "route_dinner_far_from_hotel",
                        "major",
                        day_no,
                        f"晚餐距离当天酒店过远：{dinner.get('location') or dinner.get('title')} 到酒店约 {distance:.1f}km",
                    )
                )

    closing = activities[-1]
    closing_coord = _activity_coord(closing)
    if closing_coord:
        distance = _distance_km(closing_coord, hotel_coord)
        if distance > CLOSING_HOTEL_MAX_KM:
            issues.append(
                _issue(
                    "route_closing_far_from_hotel",
                    "major",
                    day_no,
                    f"最后一站距离当天酒店过远：{closing.get('location') or closing.get('title')} 到酒店约 {distance:.1f}km",
                )
            )
    return issues


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


def _name_key(value: Any) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]", "", str(value or "")).lower()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        matched = re.search(r"\d+(?:\.\d+)?", str(value or ""))
        return int(float(matched.group())) if matched else default
    except Exception:
        return default


def _start_time(value: Any) -> str:
    return str(value or "").split("-", 1)[0].strip()


def _start_hour(value: Any) -> float | None:
    matched = re.search(r"(\d{1,2})(?::(\d{2}))?", str(value or ""))
    if not matched:
        return None
    return int(matched.group(1)) + int(matched.group(2) or 0) / 60


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


def _classify_activity_category(activity: Dict[str, Any]) -> str:
    text = " ".join(
        [
            str(activity.get("title", "")),
            str(activity.get("type", "")),
            str(activity.get("description", "")),
            str(activity.get("location", "")),
        ]
    )
    if any(token in text for token in ("早餐", "午餐", "晚餐", "餐", "美食", "小吃", "咖啡", "茶馆", "火锅", "面")):
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


def _intercity_leg(intercity_transport: Dict[str, Any], key: str) -> Dict[str, Any] | None:
    leg = intercity_transport.get(key) if isinstance(intercity_transport, dict) else None
    return leg if isinstance(leg, dict) and leg.get("from") and leg.get("to") else None


def _has_intercity_direction(activities: List[Dict[str, Any]], direction: str) -> bool:
    return any(_is_intercity_transport_activity(activity) and str(activity.get("intercity_direction") or activity.get("direction") or "") == direction for activity in activities)


def _is_intercity_transport_activity(activity: Dict[str, Any]) -> bool:
    if activity.get("is_intercity_transport"):
        return True
    text = _activity_text(activity)
    has_transport = any(token in text for token in RETURN_TRANSPORT_TOKENS)
    has_trip_edge = any(token in text for token in ("去程", "返程", "出发地", "目的地", "返回出发地"))
    return has_transport and has_trip_edge


def _is_synthetic_intercity_transport_activity(activity: Dict[str, Any], intercity_transport: Dict[str, Any]) -> bool:
    if activity.get("is_intercity_transport"):
        return False

    text = _activity_text(activity)
    title = str(activity.get("title") or "").strip()
    if any(token in text for token in INTERCITY_ACTIVITY_TOKENS):
        return True

    for key in ("outbound", "inbound"):
        leg = _intercity_leg(intercity_transport, key)
        if leg and _leg_city_pair_in_text(leg, text) and any(token in text for token in RETURN_TRANSPORT_TOKENS):
            return True

    has_route_connector = bool(re.search(r".+(至|到|→|->).+", title))
    return has_route_connector and any(token in title for token in ("交通", "车", "高铁", "动车", "火车", "飞机", "大巴"))


def _leg_city_pair_in_text(leg: Dict[str, Any], text: str) -> bool:
    from_city = _name_key(leg.get("from", ""))
    to_city = _name_key(leg.get("to", ""))
    normalized_text = _name_key(text)
    return bool(from_city and to_city and from_city in normalized_text and to_city in normalized_text)


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
    duration = _safe_int(best_option.get("duration_minutes") or leg.get("duration_minutes"), 90)
    total_cost = _safe_int(best_option.get("total_cost") or leg.get("total_cost"), 0)
    cost_per_person = _safe_int(best_option.get("cost_per_person") or leg.get("cost_per_person"), 0)
    transport_options = _leg_transport_options(leg, best_option)
    return {
        "time": _leg_time_range(leg),
        "title": f"{label}：{from_city} → {to_city}   {mode}",
        "description": f"{label}交通安排，{departure_datetime or '时间待确认'} 出发，{arrival_datetime or '时间待确认'} 到达。",
        "type": "交通衔接",
        "location": f"{from_terminal} - {to_terminal}",
        "duration": max(duration, 30),
        "cost_estimate": total_cost,
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
        "total_cost": total_cost,
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


def _time_from_datetime(value: Any) -> str:
    matched = re.search(r"(\d{1,2}):(\d{2})", str(value or ""))
    return f"{int(matched.group(1)):02d}:{matched.group(2)}" if matched else ""


def _minutes_from_clock(value: Any) -> int | None:
    matched = re.search(r"(\d{1,2}):(\d{2})", str(value or ""))
    if not matched:
        return None
    return int(matched.group(1)) * 60 + int(matched.group(2))


def _is_dinner_activity(activity: Dict[str, Any]) -> bool:
    text = _activity_text(activity)
    hour = _start_hour(activity.get("time"))
    return "晚餐" in text or "晚饭" in text or (hour is not None and hour >= 17)


def _activities_after_return_terminal(activities: List[Dict[str, Any]]) -> List[str]:
    terminal_index = _return_terminal_index(activities)
    if terminal_index is None:
        return []
    terminal_hour = _start_hour(activities[terminal_index].get("time"))
    result: List[str] = []
    for index, activity in enumerate(activities):
        if index == terminal_index:
            continue
        activity_hour = _start_hour(activity.get("time"))
        is_after = index > terminal_index
        if terminal_hour is not None and activity_hour is not None:
            is_after = activity_hour > terminal_hour
        if is_after:
            result.append(str(activity.get("location") or activity.get("title") or "").strip())
    return [item for item in result if item]


def _trim_after_return_terminal_for_review(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    terminal_index = _return_terminal_index(activities)
    if terminal_index is None:
        return activities
    terminal = activities[terminal_index]
    terminal_hour = _start_hour(terminal.get("time"))
    kept: List[Dict[str, Any]] = []
    for index, activity in enumerate(activities):
        if index == terminal_index:
            continue
        activity_hour = _start_hour(activity.get("time"))
        remove_activity = index > terminal_index
        if terminal_hour is not None and activity_hour is not None:
            remove_activity = activity_hour > terminal_hour
        if not remove_activity:
            kept.append(activity)
    kept.append(terminal)
    return sorted(kept, key=lambda item: _time_sort_key(item.get("time")))


def _return_terminal_index(activities: List[Dict[str, Any]]) -> int | None:
    indexes = [index for index, activity in enumerate(activities) if _is_return_terminal_activity(activity)]
    if not indexes:
        return None
    return min(
        indexes,
        key=lambda index: (_start_hour(activities[index].get("time")) if _start_hour(activities[index].get("time")) is not None else 24.0, index),
    )


def _is_return_terminal_activity(activity: Dict[str, Any]) -> bool:
    if _is_intercity_transport_activity(activity) and str(activity.get("intercity_direction") or activity.get("direction") or "") == "inbound":
        return True
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


def _title_location_mismatch(activity: Dict[str, Any]) -> bool:
    if _classify_activity_category(activity) == "food" or _is_intercity_transport_activity(activity):
        return False
    title = str(activity.get("title") or "").strip()
    location = str(activity.get("location") or "").strip()
    if not title or not location:
        return False
    if _looks_like_transport_title(title):
        return True
    title_key = _name_key(re.sub(r"^(探访|游览|打卡|漫步|探索|体验)[：:\s-]*", "", title))
    location_key = _name_key(location)
    if not title_key or not location_key:
        return False
    return bool(activity.get("source_id") or activity.get("coordinates")) and location_key not in title_key and title_key not in location_key


def _activity_closed_at_scheduled_time(activity: Dict[str, Any]) -> bool:
    if _is_intercity_transport_activity(activity):
        return False
    start = _minutes_from_clock(_start_time(activity.get("time")))
    if start is None:
        return False
    duration = max(min(_safe_int(activity.get("duration"), 90), 120), 45)
    return not _activity_available_at(activity, start, duration)


def _activity_available_at(activity: Dict[str, Any], start: int, duration: int) -> bool:
    ranges = _opening_ranges_minutes(activity)
    if ranges:
        return any(start >= open_at and start + duration <= close_at for open_at, close_at in ranges)
    if _is_daytime_only_activity(activity):
        return start + min(duration, 60) <= 18 * 60
    return True


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


def _meal_time_conflict(activity: Dict[str, Any]) -> str:
    if _classify_activity_category(activity) != "food":
        return ""
    text = " ".join(
        str(activity.get(key, "") or "")
        for key in ("title", "type", "description", "location")
    )
    hour = _start_hour(activity.get("time"))
    if hour is None:
        return ""
    place = str(activity.get("location") or activity.get("title") or "").strip()
    if ("晚餐" in text or "晚饭" in text) and hour < 16:
        return f"餐别与时间冲突：{place} 标为晚餐但安排在 {activity.get('time')}"
    if ("午餐" in text or "午饭" in text) and hour >= 16:
        return f"餐别与时间冲突：{place} 标为午餐但安排在 {activity.get('time')}"
    if "下午茶" in text and (hour < 14 or hour >= 18):
        return f"餐别与时间冲突：{place} 标为下午茶但安排在 {activity.get('time')}"
    return ""


def _pick_replacement_candidate(state: Dict[str, Any], used_locations: set[str], category: str) -> Dict[str, Any] | None:
    candidate_groups = []
    if category == "food":
        candidate_groups.append(state.get("food_candidates", []) or [])
    else:
        candidate_groups.append(state.get("attraction_candidates", []) or [])

    for group in candidate_groups:
        for item in group:
            name = str(item.get("name", "")).strip()
            name_key = _name_key(name)
            if name and name_key and name_key not in used_locations:
                used_locations.add(name_key)
                return dict(item)
    return None


def _pick_nearest_candidate(
    state: Dict[str, Any],
    used_locations: set[str],
    category: str,
    anchor: tuple[float, float] | None,
) -> Dict[str, Any] | None:
    if not anchor:
        return _pick_replacement_candidate(state, used_locations, category)

    if category == "food":
        groups = [state.get("scored_foods") or state.get("food_candidates") or []]
    else:
        groups = [state.get("scored_attractions") or state.get("attraction_candidates") or []]

    ranked: List[tuple[float, float, Dict[str, Any]]] = []
    for group in groups:
        for item in group:
            name = str(item.get("name", "")).strip()
            name_key = _name_key(name)
            coord = _coord_from_mapping(item)
            if not name or not name_key or name_key in used_locations or not coord:
                continue
            ranked.append((_distance_km(coord, anchor), -float(item.get("score", 0) or 0), dict(item)))

    if not ranked:
        return _pick_replacement_candidate(state, used_locations, category)
    ranked.sort(key=lambda item: (item[0], item[1]))
    picked = ranked[0][2]
    used_locations.add(_name_key(picked.get("name", "")))
    return picked


def _pick_time_fit_candidate(
    state: Dict[str, Any],
    used_locations: set[str],
    category: str,
    activity: Dict[str, Any],
    anchor: tuple[float, float] | None,
) -> Dict[str, Any] | None:
    start = _minutes_from_clock(_start_time(activity.get("time")))
    duration = max(min(_safe_int(activity.get("duration"), 90), 120), 45)
    if start is None:
        return _pick_nearest_candidate(state, used_locations, category, anchor)

    if category == "food":
        groups = [state.get("scored_foods") or state.get("food_candidates") or []]
    else:
        groups = [state.get("scored_attractions") or state.get("attraction_candidates") or []]

    ranked: List[tuple[float, float, Dict[str, Any]]] = []
    for group in groups:
        for item in group:
            name = str(item.get("name", "")).strip()
            name_key = _name_key(name)
            if not name or not name_key or name_key in used_locations:
                continue
            probe = {
                "title": name,
                "location": name,
                "description": item.get("description", ""),
                "opening_hours": item.get("opening_hours", ""),
            }
            if not _activity_available_at(probe, start, duration):
                continue
            coord = _coord_from_mapping(item)
            distance = _distance_km(coord, anchor) if coord and anchor else 0.0
            ranked.append((distance, -float(item.get("score", 0) or 0), dict(item)))

    if not ranked:
        return _pick_nearest_candidate(state, used_locations, category, anchor)
    ranked.sort(key=lambda item: (item[0], item[1]))
    picked = ranked[0][2]
    used_locations.add(_name_key(picked.get("name", "")))
    return picked


def _apply_candidate_to_activity(activity: Dict[str, Any], candidate: Dict[str, Any], category: str) -> None:
    name = str(candidate.get("name", "")).strip()
    if name:
        old_location = str(activity.get("location", "") or "").strip()
        activity["location"] = name
        if category != "food":
            activity["title"] = name
        else:
            title = str(activity.get("title", "") or name)
            activity["title"] = title.replace(old_location, name) if old_location else title
    details = [
        str(candidate.get("description", "") or "").strip(),
        str(candidate.get("address", "") or "").strip(),
        str(candidate.get("opening_hours", "") or "").strip(),
    ]
    activity["description"] = "；".join([item for item in details if item][:3]) or f"基于真实候选结果调整为 {name}。"
    activity["source"] = candidate.get("source", "")
    activity["source_id"] = candidate.get("id", "")
    if candidate.get("opening_hours"):
        activity["opening_hours"] = candidate.get("opening_hours")
    if candidate.get("score") is not None:
        activity["score"] = candidate.get("score")
    coord = _coord_from_mapping(candidate)
    if coord:
        lat, lng = coord
        activity["coordinates"] = {"lat": lat, "lng": lng}
        activity["lat"] = lat
        activity["lng"] = lng
    if category == "food":
        activity["type"] = "美食餐饮"
        activity["ticket_price"] = 0
        if candidate.get("price"):
            activity["cost_estimate"] = _safe_int(candidate.get("price"), activity.get("cost_estimate", 90))


def _normalize_activity_times(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    intercity_activities = [dict(activity) for activity in activities if _is_intercity_transport_activity(activity)]
    filtered = [dict(activity) for activity in activities if not _is_hotel_activity(activity) and not _is_intercity_transport_activity(activity)]
    terminal = None
    terminal_index = _return_terminal_index(filtered)
    if terminal_index is not None:
        terminal = filtered.pop(terminal_index)
    food_indexes = [index for index, activity in enumerate(filtered) if _classify_activity_category(activity) == "food"]
    has_evening = any(_is_evening_activity(activity) for activity in filtered if _classify_activity_category(activity) != "food")
    cursor = 9 * 60 + 30
    outbound = [activity for activity in intercity_activities if str(activity.get("intercity_direction") or activity.get("direction") or "") == "outbound"]
    inbound = [activity for activity in intercity_activities if str(activity.get("intercity_direction") or activity.get("direction") or "") == "inbound"]
    if outbound:
        arrival_minutes = _minutes_from_clock(_time_from_datetime(outbound[0].get("arrival_datetime")) or str(outbound[0].get("arrival_time") or ""))
        if arrival_minutes is not None:
            cursor = max(cursor, arrival_minutes + 45)
    inbound_departure = None
    if inbound:
        inbound_departure = _minutes_from_clock(_time_from_datetime(inbound[0].get("departure_datetime")) or str(inbound[0].get("departure_time") or ""))
    result: List[Dict[str, Any]] = []
    used_meals: set[str] = set()
    for index, activity in enumerate(filtered):
        if len(result) >= 6:
            break
        next_activity = dict(activity)
        if _classify_activity_category(next_activity) == "food":
            meal_kind = _scheduled_meal_kind(index, food_indexes, next_activity)
            if meal_kind in used_meals:
                if meal_kind != "dinner" and "tea" not in used_meals and cursor < 17 * 60:
                    meal_kind = "tea"
                else:
                    continue
            start = _meal_start_minutes(meal_kind, cursor, has_evening)
            duration = _meal_duration_minutes(meal_kind)
            next_start = _next_available_activity_start(next_activity, start, duration, inbound_departure - 60 if inbound_departure is not None else None)
            if next_start is None:
                continue
            start = next_start
            if inbound_departure is not None and start + duration > inbound_departure - 60:
                continue
            next_activity["time"] = _format_time_range(start, duration)
            cursor = start + duration + 20
            used_meals.add(meal_kind)
            next_activity = _normalize_meal_activity(next_activity, meal_kind)
        else:
            duration = max(min(_safe_int(next_activity.get("duration"), 90), 120), 60)
            start = _activity_start_minutes(next_activity, cursor)
            next_start = _next_available_activity_start(next_activity, start, duration, inbound_departure - 60 if inbound_departure is not None else None)
            if next_start is None:
                continue
            start = next_start
            if inbound_departure is not None and start + duration > inbound_departure - 60:
                continue
            next_activity["time"] = _format_time_range(start, duration)
            cursor = start + duration + 20
        result.append(next_activity)
    if terminal:
        terminal = dict(terminal)
        terminal.setdefault("type", "交通衔接")
        terminal["is_terminal_transport"] = True
        if _start_hour(terminal.get("time")) is None:
            previous_end = _end_minutes(result[-1].get("time")) if result else None
            start = max(previous_end + 30 if previous_end is not None else 15 * 60, 15 * 60)
            terminal["time"] = _format_time_range(start, max(_safe_int(terminal.get("duration"), 90), 60))
        result.append(terminal)
    return sorted([*outbound, *result, *inbound], key=lambda item: _time_sort_key(item.get("time")))


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


def _is_evening_activity(activity: Dict[str, Any]) -> bool:
    hour = _start_hour(activity.get("time"))
    if hour is not None and hour >= 18:
        return not _is_daytime_only_activity(activity)
    text = _activity_text(activity)
    return any(token in text for token in EVENING_ACTIVITY_TOKENS)


def _format_time_range(start_minutes: int, duration_minutes: int) -> str:
    start_minutes = max(0, min(start_minutes, 23 * 60))
    end_minutes = max(start_minutes + 30, min(start_minutes + duration_minutes, 23 * 60 + 30))
    return f"{_format_clock(start_minutes)}-{_format_clock(end_minutes)}"


def _format_clock(total_minutes: int) -> str:
    hours = max(0, total_minutes // 60)
    minutes = max(0, total_minutes % 60)
    return f"{hours:02d}:{minutes:02d}"


def _scheduled_meal_kind(index: int, food_indexes: List[int], activity: Dict[str, Any]) -> str:
    position = food_indexes.index(index) if index in food_indexes else 0
    if len(food_indexes) == 1:
        hour = _start_hour(activity.get("time"))
        if hour is not None and hour >= 16:
            return "dinner"
        return "lunch"
    if position == len(food_indexes) - 1:
        return "dinner"
    if len(food_indexes) >= 3 and position == len(food_indexes) - 2:
        return "tea"
    return "lunch"


def _normalize_meal_activity(activity: Dict[str, Any], meal_kind: str) -> Dict[str, Any]:
    labels = {"breakfast": "早餐", "lunch": "午餐", "tea": "下午茶", "dinner": "晚餐"}
    label = labels.get(meal_kind, "用餐")
    next_activity = dict(activity)
    location = str(next_activity.get("location") or "").strip()
    title = str(next_activity.get("title") or location or label).strip()
    title = re.sub(r"^(早餐|早茶|早午茶|午餐|午饭|下午茶|晚餐|晚饭|夜宵)[：:\s-]*", "", title).strip()
    if _looks_like_transport_title(title):
        title = location
    next_activity["title"] = f"{label}：{title or location or '餐饮安排'}"
    next_activity["type"] = "美食餐饮"
    next_activity["ticket_price"] = 0
    return next_activity


def _looks_like_transport_title(value: Any) -> bool:
    text = str(value or "")
    return any(token in text for token in TRANSPORT_TITLE_TOKENS)


def _dedupe_dinner_activities(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    dinner_seen = False
    for activity in activities:
        if _classify_activity_category(activity) == "food" and _is_dinner_activity(activity):
            if dinner_seen:
                continue
            dinner_seen = True
        result.append(activity)
    return result


def _patch_itinerary(plan: List[Dict[str, Any]], state: Dict[str, Any], issues: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    patched = normalize_itinerary(plan, state)
    patch_actions: List[Dict[str, Any]] = []
    used_locations = {
        _name_key(activity.get("location", ""))
        for day in patched
        for activity in (day.get("activities", []) or [])
        if _name_key(activity.get("location", ""))
    }

    for issue in issues:
        day_no = issue.get("day")
        if not isinstance(day_no, int) or day_no <= 0 or day_no > len(patched):
            continue
        day = patched[day_no - 1]
        activities = day.get("activities", []) or []
        hotel_coord = _day_hotel_coord(day, state)
        intercity_transport = state.get("intercity_transport") or (state.get("transport_plan") or {}).get("intercity_transport") or {}

        if issue["type"] == "hotel_activity_in_timeline":
            before_count = len(activities)
            activities = [activity for activity in activities if not _is_hotel_activity(activity)]
            if len(activities) != before_count:
                patch_actions.append({"day": day_no, "action": "remove_hotel_activity"})

        elif issue["type"] == "duplicate_intercity_activity":
            before_count = len(activities)
            activities = [
                activity
                for activity in activities
                if not _is_synthetic_intercity_transport_activity(activity, intercity_transport)
            ]
            if len(activities) != before_count:
                patch_actions.append({"day": day_no, "action": "remove_duplicate_intercity_activity"})

        elif issue["type"] == "activity_after_return":
            before_count = len(activities)
            activities = _trim_after_return_terminal_for_review(activities)
            if len(activities) != before_count:
                patch_actions.append({"day": day_no, "action": "remove_after_return_terminal"})

        elif issue["type"] == "missing_outbound_transport":
            outbound = _intercity_leg(intercity_transport, "outbound")
            if outbound:
                activities = [_transport_activity_from_leg(outbound), *activities]
                patch_actions.append({"day": day_no, "action": "insert_outbound_transport"})

        elif issue["type"] == "missing_inbound_transport":
            inbound = _intercity_leg(intercity_transport, "inbound")
            if inbound:
                activities = _trim_after_return_terminal_for_review([*activities, _transport_activity_from_leg(inbound)])
                patch_actions.append({"day": day_no, "action": "insert_inbound_transport"})

        elif issue["type"] == "duplicate_dinner":
            activities = _dedupe_dinner_activities(activities)
            patch_actions.append({"day": day_no, "action": "dedupe_dinner"})

        elif issue["type"] in {"duplicate_start_time", "meal_time_conflict"}:
            patch_actions.append({"day": day_no, "action": "normalize_activity_times", "reason": issue["type"]})

        elif issue["type"] == "title_location_mismatch":
            for activity in activities:
                if _title_location_mismatch(activity):
                    location = str(activity.get("location") or "").strip()
                    if location:
                        activity["title"] = location
                        patch_actions.append({"day": day_no, "action": "align_title_with_location", "location": location})

        elif issue["type"] == "closed_at_time":
            repaired: List[Dict[str, Any]] = []
            for activity in activities:
                if not _activity_closed_at_scheduled_time(activity):
                    repaired.append(activity)
                    continue
                category = _classify_activity_category(activity)
                original_name = str(activity.get("location") or activity.get("title") or "").strip()
                replacement = _pick_time_fit_candidate(state, used_locations, category, activity, hotel_coord)
                replacement_name = str((replacement or {}).get("name", "")).strip()
                if replacement_name:
                    next_activity = dict(activity)
                    _apply_candidate_to_activity(next_activity, replacement, category)
                    repaired.append(next_activity)
                    patch_actions.append({"day": day_no, "action": "replace_closed_activity", "from": original_name, "to": replacement_name})
                else:
                    patch_actions.append({"day": day_no, "action": "remove_closed_activity", "from": original_name})
            activities = repaired

        elif issue["type"] == "missing_food":
            replacement = _pick_replacement_candidate(state, used_locations, "food")
            replacement_name = str((replacement or {}).get("name", "")).strip()
            if replacement_name:
                activities.insert(
                    min(2, len(activities)),
                    {
                        "time": "12:30-13:30",
                        "title": "补充本地特色用餐",
                        "description": f"根据 review 自动补充更合理的餐饮安排，优先使用真实餐饮候选 {replacement_name}。",
                        "type": "美食餐饮",
                        "location": replacement_name,
                        "duration": 60,
                        "cost_estimate": 90,
                        "ticket_price": 0,
                        "tips": "建议错峰到店。",
                        "transportation": "步行/网约车",
                        "source": replacement.get("source", ""),
                        "source_id": replacement.get("id", ""),
                    },
                )
                patch_actions.append({"day": day_no, "action": "insert_food", "location": replacement_name})

        elif issue["type"] == "missing_activities":
            while len(activities) < 5:
                replacement = _pick_replacement_candidate(state, used_locations, "attraction")
                candidate_location = str((replacement or {}).get("name", "")).strip()
                if not candidate_location:
                    break
                next_activity = {
                    "time": "15:30-17:00",
                    "title": candidate_location,
                    "description": f"基于真实候选结果补充的行程活动：{candidate_location}。",
                    "type": "景点游览",
                    "location": candidate_location,
                    "duration": 90,
                    "cost_estimate": 0,
                    "ticket_price": 0,
                    "tips": "建议根据开放时间调整顺序。",
                    "transportation": "步行/网约车",
                    "source": replacement.get("source", ""),
                    "source_id": replacement.get("id", ""),
                }
                activities.append(next_activity)
                patch_actions.append({"day": day_no, "action": "append_activity", "location": next_activity.get("location", "")})

        elif issue["type"] == "duplicate_location":
            duplicate_name = issue["message"].split("：", 1)[-1].strip()
            replaced = False
            for activity in activities:
                if str(activity.get("location", "")).strip() != duplicate_name:
                    continue
                category = _classify_activity_category(activity)
                replacement = _pick_replacement_candidate(state, used_locations, category)
                replacement_name = str((replacement or {}).get("name", "")).strip()
                if replacement_name and replacement_name != duplicate_name:
                    activity["location"] = replacement_name
                    activity["title"] = (
                        replacement_name
                        if category != "food"
                        else str(activity.get("title", "")).replace(duplicate_name, replacement_name) or replacement_name
                    )
                    activity["description"] = f"基于真实候选结果替换重复地点，调整为 {replacement_name}。"
                    activity["source"] = replacement.get("source", "")
                    activity["source_id"] = replacement.get("id", "")
                    patch_actions.append({"day": day_no, "action": "replace_duplicate", "from": duplicate_name, "to": replacement_name})
                    replaced = True
                    break

        elif issue["type"] == "route_dinner_far_from_hotel":
            food_indexes = [index for index, activity in enumerate(activities) if _classify_activity_category(activity) == "food"]
            if food_indexes:
                dinner_index = food_indexes[-1]
                original_name = str(activities[dinner_index].get("location") or activities[dinner_index].get("title") or "").strip()
                replacement = _pick_nearest_candidate(state, used_locations, "food", hotel_coord)
                replacement_name = str((replacement or {}).get("name", "")).strip()
                if replacement_name and replacement_name != original_name:
                    _apply_candidate_to_activity(activities[dinner_index], replacement, "food")
                    patch_actions.append({"day": day_no, "action": "replace_dinner_near_hotel", "from": original_name, "to": replacement_name})

        elif issue["type"] == "route_closing_far_from_hotel":
            if activities:
                original_name = str(activities[-1].get("location") or activities[-1].get("title") or "").strip()
                category = _classify_activity_category(activities[-1])
                replacement = _pick_nearest_candidate(state, used_locations, category, hotel_coord)
                replacement_name = str((replacement or {}).get("name", "")).strip()
                if replacement_name and replacement_name != original_name:
                    _apply_candidate_to_activity(activities[-1], replacement, category)
                    patch_actions.append({"day": day_no, "action": "replace_closing_near_hotel", "from": original_name, "to": replacement_name})

        elif issue["type"] == "missing_hotel":
            hotel_options = state.get("hotel_options", []) or []
            if hotel_options:
                hotel = hotel_options[0]
                day["hotel_recommendation"] = {
                    "name": hotel.get("name", state["city"]),
                    "price_estimate": hotel.get("price", ""),
                    "address": hotel.get("address", state["city"]),
                    "reason": "review 阶段自动补充住宿建议，确保每日行程闭环。",
                }
                patch_actions.append({"day": day_no, "action": "fill_hotel", "location": hotel.get("name", "")})

        day["activities"] = _normalize_activity_times(activities[:6])

    return normalize_itinerary(patched, state), patch_actions


def _needs_rerun(issues: List[Dict[str, Any]], patch_actions: List[Dict[str, Any]], state: Dict[str, Any]) -> bool:
    if not issues:
        return False
    major_count = len([issue for issue in issues if issue.get("severity") == "major"])
    if major_count >= 2:
        return task_can_retry(state, "synthesizer_agent")
    if len(issues) >= max(4, state.get("days", 1) * 2) and len(patch_actions) < len(issues) // 2:
        return task_can_retry(state, "synthesizer_agent")
    return False


def reviewer_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    draft_plan = state.get("plan") or state.get("draft_plan") or []
    reviewed_plan = normalize_itinerary(draft_plan, state)
    review_issues = _review_itinerary(reviewed_plan, state)
    patched_plan, patch_actions = _patch_itinerary(reviewed_plan, state, review_issues)
    post_patch_issues = _review_itinerary(patched_plan, state)
    reflection_history = list(state.get("reflection_history", []) or [])

    rerun_required = _needs_rerun(post_patch_issues, patch_actions, state)
    review_summary = (
        f"发现 {len(review_issues)} 个问题，已自动修补 {len(patch_actions)} 处。"
        if review_issues
        else "未发现明显问题，行程可直接进入后处理。"
    )

    reflection_entry = {
        "summary": review_summary,
        "issue_count": len(review_issues),
        "post_patch_issue_count": len(post_patch_issues),
        "patch_actions": patch_actions,
        "rerun_required": rerun_required,
    }
    reflection_history.append(ReflectionHistoryEntryModel.model_validate(reflection_entry).model_dump())

    result = {
        "plan": patched_plan,
        "reviewed_plan": patched_plan,
        "review_issues": post_patch_issues,
        "quality_score": _quality_score(patched_plan, post_patch_issues, state),
        "reflection_history": reflection_history,
    }

    if rerun_required:
        completion = complete_task(
            state,
            "reviewer_agent",
            build_task_result(
                output={"patch_actions": patch_actions, "rerun_required": rerun_required},
                metrics={
                    "issue_count": len(review_issues),
                    "post_patch_issue_count": len(post_patch_issues),
                    "patch_count": len(patch_actions),
                },
                trace=patch_actions,
                quality={"status": "rerun"},
                summary=review_summary,
            ),
        )
        rerun_state = {**state, **completion}
        result.update(
            {
                "reflection_context": ReflectionContextModel(
                    action="rerun_synthesizer",
                    summary=review_summary,
                    issues=[ReviewIssueModel.model_validate(issue) for issue in post_patch_issues],
                ).model_dump()
            }
        )
        result.update(
            reset_task_chain(
                rerun_state,
                ["synthesizer_agent", "poi_agent", "reviewer_agent"],
                reason="reflection requested synthesizer rerun",
            )
        )
    else:
        result.update(
            complete_task(
                state,
                "reviewer_agent",
                build_task_result(
                    output={"patch_actions": patch_actions, "rerun_required": rerun_required},
                    metrics={
                        "issue_count": len(review_issues),
                        "post_patch_issue_count": len(post_patch_issues),
                        "patch_count": len(patch_actions),
                    },
                    trace=patch_actions,
                    quality={"status": "patched" if patch_actions else "passed"},
                    summary=review_summary,
                ),
            )
        )
    return result
