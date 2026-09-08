from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Tuple

from app.trip_planning.constants import DEFAULT_MODE_DURATIONS, TRANSPORT_MODE_RULES

logger = logging.getLogger(__name__)


def plan_intercity_transport(
    departure_city: str | None,
    destination_city: str | None,
    travelers: int = 1,
    *,
    start_date: str | None = None,
    outbound_departure_datetime: str | None = None,
    return_arrival_datetime: str | None = None,
    days: int = 1,
    budget_amount: int | float | None = None,
    budget_level: str | None = None,
    preferences: list[str] | None = None,
) -> Dict[str, Any]:
    departure = str(departure_city or "").strip()
    destination = str(destination_city or "").strip()
    if not departure or not destination:
        return {}

    traveler_count = max(int(travelers or 1), 1)
    travel_days = max(int(days or 1), 1)
    outbound_departure_at = _parse_datetime(outbound_departure_datetime)
    return_arrival_at = _parse_datetime(return_arrival_datetime)
    trip_start = (outbound_departure_at.date() if outbound_departure_at else None) or _parse_date(start_date) or date.today()
    if return_arrival_at and return_arrival_at.date() >= trip_start:
        travel_days = max(travel_days, (return_arrival_at.date() - trip_start).days + 1)

    if _normalize_city_name(departure) == _normalize_city_name(destination):
        outbound = _same_city_leg(
            departure,
            destination,
            traveler_count,
            "outbound",
            outbound_departure_at or datetime.combine(trip_start, time(9, 0)),
        )
        inbound = _same_city_leg(
            destination,
            departure,
            traveler_count,
            "inbound",
            return_arrival_at or datetime.combine(trip_start + timedelta(days=travel_days - 1), time(18, 0)),
        )
        return _assemble_plan(departure, destination, traveler_count, outbound, inbound)

    # The execution layer must be deterministic and bounded. Use real map
    # distance as the primary signal instead of starting another nested LLM
    # call inside the agent's transport tool.
    route_metrics = _query_route_metrics(departure, destination)
    if route_metrics:
        distance_km, route_duration_minutes = route_metrics
        outbound = _build_leg(
            direction="outbound",
            from_city=departure,
            to_city=destination,
            distance_km=distance_km,
            route_duration_minutes=route_duration_minutes,
            travelers=traveler_count,
            trip_start=trip_start,
            travel_days=travel_days,
            outbound_departure_at=outbound_departure_at,
            return_arrival_at=return_arrival_at,
            source="map",
        )
        inbound = _build_leg(
            direction="inbound",
            from_city=destination,
            to_city=departure,
            distance_km=distance_km,
            route_duration_minutes=route_duration_minutes,
            travelers=traveler_count,
            trip_start=trip_start,
            travel_days=travel_days,
            outbound_departure_at=outbound_departure_at,
            return_arrival_at=return_arrival_at,
            source="map",
        )
        return _assemble_plan(
            departure,
            destination,
            traveler_count,
            outbound,
            inbound,
            distance_km=distance_km,
        )

    outbound = _build_fallback_leg(
        direction="outbound",
        from_city=departure,
        to_city=destination,
        travelers=traveler_count,
        trip_start=trip_start,
        travel_days=travel_days,
        outbound_departure_at=outbound_departure_at,
        return_arrival_at=return_arrival_at,
    )
    inbound = _build_fallback_leg(
        direction="inbound",
        from_city=destination,
        to_city=departure,
        travelers=traveler_count,
        trip_start=trip_start,
        travel_days=travel_days,
        outbound_departure_at=outbound_departure_at,
        return_arrival_at=return_arrival_at,
    )
    outbound["note"] = "地图距离暂不可用，系统仅给出待确认的候选模板，建议出行前核对实时票价与站点。"
    inbound["note"] = outbound["note"]
    return _assemble_plan(departure, destination, traveler_count, outbound, inbound)


def _assemble_plan(
    departure: str,
    destination: str,
    travelers: int,
    outbound: Dict[str, Any],
    inbound: Dict[str, Any],
    *,
    distance_km: float | None = None,
) -> Dict[str, Any]:
    total_cost = int(outbound.get("total_cost", 0) or 0) + int(inbound.get("total_cost", 0) or 0)
    plan = {
        "departure_city": departure,
        "destination": destination,
        "currency": "CNY",
        "estimated": bool(outbound.get("estimated", True) or inbound.get("estimated", True)),
        "cost_pending": False,
        "total_cost": total_cost,
        "cost_per_person": int(total_cost / max(travelers, 1)),
        "outbound": outbound,
        "inbound": inbound,
        "summary": f"往返大交通预计 {total_cost} 元，已按 {travelers} 人计入交通预算。",
    }
    if distance_km:
        plan["distance_km"] = round(distance_km, 1)
    return plan


def _normalize_city_name(value: str) -> str:
    text = re.sub(r"\s+", "", str(value or "")).strip()
    for suffix in ("特别行政区", "自治区", "自治州", "地区", "城市", "市", "省", "县", "区"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return text


def _same_city_leg(from_city: str, to_city: str, travelers: int, direction: str, depart_at: datetime) -> Dict[str, Any]:
    option = _build_transport_option(
        source={},
        direction=direction,
        from_city=from_city,
        to_city=to_city,
        travelers=travelers,
        fallback_departure=depart_at,
        fallback_duration=0,
        anchor_departure=depart_at if direction == "outbound" else None,
        anchor_arrival=depart_at if direction == "inbound" else None,
        default_mode="市内交通",
        default_from_terminal=from_city,
        default_to_terminal=to_city,
        source_name="same_city",
    )
    option["duration_minutes"] = 0
    option["duration_text"] = "无需大交通"
    option["cost_per_person"] = 0
    option["total_cost"] = 0
    leg = _leg_from_options(
        direction=direction,
        from_city=from_city,
        to_city=to_city,
        travelers=travelers,
        best_option=option,
        alternatives=[],
        source="same_city",
    )
    leg.update(
        {
            "duration_minutes": 0,
            "duration_text": "无需大交通",
            "cost_per_person": 0,
            "total_cost": 0,
            "note": f"按 {travelers} 人计算，出发城市与目的地相同。",
        }
    )
    return leg


def _query_route_metrics(from_city: str, to_city: str) -> Tuple[float, int] | None:
    try:
        from app.domain import travel_domain_service

        origin = _resolve_city_coordinate(from_city)
        destination = _resolve_city_coordinate(to_city)
        if not origin or not destination:
            return None

        route = travel_domain_service.calculate_route(
            _format_route_coordinate(origin),
            _format_route_coordinate(destination),
            "driving",
        )
        distance_meters = float(route.get("distance") or 0)
        duration_seconds = int(float(route.get("duration") or 0))
        if distance_meters <= 0:
            return None
        return distance_meters / 1000, max(duration_seconds // 60, 0)
    except Exception as exc:
        logger.debug("Intercity route metrics unavailable: %s", exc)
        return None


def _resolve_city_coordinate(city: str) -> Tuple[float, float] | None:
    from app.domain import travel_domain_service

    items = travel_domain_service.search_pois(city, city, 1, 1)
    for item in items or []:
        lat = _safe_float(item.get("lat"))
        lng = _safe_float(item.get("lng"))
        if lat and lng:
            return lat, lng
    return None


def _format_route_coordinate(point: Tuple[float, float]) -> str:
    lat, lng = point
    return f"{lng},{lat}"


def _scheduled_leg_datetimes(
    direction: str,
    trip_start: date,
    travel_days: int,
    duration_minutes: int,
    outbound_departure_at: datetime | None,
    return_arrival_at: datetime | None,
) -> Tuple[datetime, datetime]:
    if direction == "outbound" and outbound_departure_at:
        depart_at = outbound_departure_at
        return depart_at, depart_at + timedelta(minutes=duration_minutes)
    if direction == "inbound" and return_arrival_at:
        arrive_at = return_arrival_at
        return arrive_at - timedelta(minutes=duration_minutes), arrive_at
    depart_at = _default_departure_datetime(direction, trip_start, travel_days, duration_minutes)
    return depart_at, depart_at + timedelta(minutes=duration_minutes)


def _build_leg(
    *,
    direction: str,
    from_city: str,
    to_city: str,
    distance_km: float,
    route_duration_minutes: int,
    travelers: int,
    trip_start: date,
    travel_days: int,
    outbound_departure_at: datetime | None,
    return_arrival_at: datetime | None,
    source: str,
) -> Dict[str, Any]:
    mode, duration_minutes, cost_per_person = _estimate_mode_time_cost(distance_km, route_duration_minutes)
    depart_at, arrive_at = _scheduled_leg_datetimes(
        direction,
        trip_start,
        travel_days,
        duration_minutes,
        outbound_departure_at,
        return_arrival_at,
    )
    total_cost = int(cost_per_person * travelers)
    best_option = {
        "direction": direction,
        "from": from_city,
        "to": to_city,
        "mode": mode,
        "departure_datetime": _format_datetime(depart_at),
        "arrival_datetime": _format_datetime(arrive_at),
        "departure_time": depart_at.strftime("%H:%M"),
        "arrival_time": arrive_at.strftime("%H:%M"),
        "duration_minutes": duration_minutes,
        "duration_text": _format_duration(duration_minutes),
        "distance_km": round(distance_km, 1),
        "cost_per_person": cost_per_person,
        "total_cost": total_cost,
        "currency": "CNY",
        "estimated": True,
        "cost_pending": False,
        "source": source,
        "note": "基于地图路线距离估算，价格为单人单程预算参考。" if source == "map" else "系统兜底估算，建议出行前核对车次或航班。",
    }
    best_option["recommended"] = True
    alternatives = _fallback_alternatives(
        direction=direction,
        from_city=from_city,
        to_city=to_city,
        travelers=travelers,
        fallback_departure=depart_at,
        anchor_departure=outbound_departure_at if direction == "outbound" else None,
        anchor_arrival=return_arrival_at if direction == "inbound" else None,
        excluded_modes={mode},
        source_name="fallback_candidate",
    )[:3]
    return _leg_from_options(
        direction=direction,
        from_city=from_city,
        to_city=to_city,
        travelers=travelers,
        best_option=best_option,
        alternatives=alternatives,
        source=source,
    )


def _plan_with_llm(
    *,
    departure: str,
    destination: str,
    travelers: int,
    trip_start: date,
    travel_days: int,
    outbound_departure_at: datetime | None,
    return_arrival_at: datetime | None,
    budget_amount: int | float | None,
    budget_level: str | None,
    preferences: list[str],
) -> Dict[str, Any] | None:
    prompt = _build_llm_transport_prompt(
        departure=departure,
        destination=destination,
        travelers=travelers,
        trip_start=trip_start,
        travel_days=travel_days,
        outbound_departure_at=outbound_departure_at,
        return_arrival_at=return_arrival_at,
        budget_amount=budget_amount,
        budget_level=budget_level,
        preferences=preferences,
    )
    try:
        from app.core.llm import invoke_llm_with_fallback

        response = invoke_llm_with_fallback(
            prompt,
            temperature=0.2,
            max_tokens=1800,
            request_timeout=60,
            max_retries=1,
        )
        parsed = _extract_json(_message_text(response))
        outbound = _normalize_llm_leg(
            parsed.get("outbound") or {},
            direction="outbound",
            from_city=departure,
            to_city=destination,
            travelers=travelers,
            fallback_departure=_default_departure_datetime("outbound", trip_start, travel_days, 240),
            anchor_departure=outbound_departure_at,
            anchor_arrival=None,
        )
        inbound = _normalize_llm_leg(
            parsed.get("inbound") or {},
            direction="inbound",
            from_city=destination,
            to_city=departure,
            travelers=travelers,
            fallback_departure=_default_departure_datetime("inbound", trip_start, travel_days, 240),
            anchor_departure=None,
            anchor_arrival=return_arrival_at,
        )
        return _assemble_plan(departure, destination, travelers, outbound, inbound)
    except Exception as exc:
        logger.warning("LLM intercity transport planning failed: %s", exc)
        return None


def _build_llm_transport_prompt(
    *,
    departure: str,
    destination: str,
    travelers: int,
    trip_start: date,
    travel_days: int,
    outbound_departure_at: datetime | None,
    return_arrival_at: datetime | None,
    budget_amount: int | float | None,
    budget_level: str | None,
    preferences: list[str],
) -> str:
    trip_end = trip_start + timedelta(days=travel_days - 1)
    context = {
        "departure_city": departure,
        "destination": destination,
        "travelers": travelers,
        "start_date": trip_start.isoformat(),
        "end_date": trip_end.isoformat(),
        "outbound_departure_datetime": _format_datetime(outbound_departure_at) if outbound_departure_at else "",
        "return_arrival_datetime": _format_datetime(return_arrival_at) if return_arrival_at else "",
        "days": travel_days,
        "budget_amount": budget_amount or 0,
        "budget_level": budget_level or "",
        "preferences": preferences,
    }
    return f"""
你是旅行交通规划助手。请只根据出发城市、目的地城市、预算、人数和出行时间，推荐往返大交通方案。

要求：
- 只能返回合法 JSON，不要 Markdown。
- 不要按固定距离规则套用交通方式，要结合两地常识、时间效率、预算、舒适度和可执行性判断。
- 每一段都必须返回一个 best_option 和 2-4 个 alternatives。
- best_option 是你认为最合适的交通方式；alternatives 是可选交通方式，例如飞机、高铁/动车、火车、自驾、城际汽车等。
- 每个方案必须包含 mode、from_terminal、to_terminal、departure_datetime、arrival_datetime、duration_minutes、cost_per_person、reason。
- 如果上下文提供 outbound_departure_datetime，去程所有方案的 departure_datetime 必须等于该值。
- 如果上下文提供 return_arrival_datetime，返程所有方案的 arrival_datetime 必须等于该值。
- from_terminal/to_terminal 要写交通站点或机场航站楼；不确定航站楼时写主要机场/主要高铁站/主要火车站，不要写景点。
- 费用为估算票价/油费/过路费，按人民币 CNY，cost_per_person 是单人单程费用。
- 不要编造具体车次、航班号、班次号。

上下文：
{json.dumps(context, ensure_ascii=False)}

返回 JSON 结构：
{{
  "outbound": {{
    "best_option": {{
      "mode": "交通方式",
      "from_terminal": "出发站点",
      "to_terminal": "到达站点",
      "departure_datetime": "YYYY-MM-DD HH:MM",
      "arrival_datetime": "YYYY-MM-DD HH:MM",
      "duration_minutes": 180,
      "cost_per_person": 600,
      "reason": "为什么这是最佳方案"
    }},
    "alternatives": [
      {{
        "mode": "备选交通方式",
        "from_terminal": "出发站点",
        "to_terminal": "到达站点",
        "departure_datetime": "YYYY-MM-DD HH:MM",
        "arrival_datetime": "YYYY-MM-DD HH:MM",
        "duration_minutes": 420,
        "cost_per_person": 800,
        "reason": "备选理由"
      }}
    ]
  }},
  "inbound": {{
    "best_option": {{
      "mode": "交通方式",
      "from_terminal": "出发站点",
      "to_terminal": "到达站点",
      "departure_datetime": "YYYY-MM-DD HH:MM",
      "arrival_datetime": "YYYY-MM-DD HH:MM",
      "duration_minutes": 180,
      "cost_per_person": 600,
      "reason": "为什么这是最佳方案"
    }},
    "alternatives": []
  }}
}}
"""


def _normalize_llm_leg(
    source: Dict[str, Any],
    *,
    direction: str,
    from_city: str,
    to_city: str,
    travelers: int,
    fallback_departure: datetime,
    anchor_departure: datetime | None,
    anchor_arrival: datetime | None,
) -> Dict[str, Any]:
    source = source if isinstance(source, dict) else {}
    best_source = _first_dict(
        source.get("best_option"),
        source.get("bestOption"),
        source.get("recommended_option"),
        source.get("recommendedOption"),
        source.get("recommended"),
        source if source.get("mode") else None,
    )
    best_option = _build_transport_option(
        source=best_source or {},
        direction=direction,
        from_city=from_city,
        to_city=to_city,
        travelers=travelers,
        fallback_departure=fallback_departure,
        anchor_departure=anchor_departure,
        anchor_arrival=anchor_arrival,
        default_mode="交通待确认",
        default_from_terminal=f"{from_city}主要交通枢纽",
        default_to_terminal=f"{to_city}主要交通枢纽",
        source_name="llm",
    )
    best_option["recommended"] = True

    alternatives = []
    seen = {_transport_option_key(best_option)}
    for item in _transport_option_sources(source):
        option = _build_transport_option(
            source=item,
            direction=direction,
            from_city=from_city,
            to_city=to_city,
            travelers=travelers,
            fallback_departure=fallback_departure,
            anchor_departure=anchor_departure,
            anchor_arrival=anchor_arrival,
            default_mode="交通待确认",
            default_from_terminal=f"{from_city}主要交通枢纽",
            default_to_terminal=f"{to_city}主要交通枢纽",
            source_name="llm",
        )
        key = _transport_option_key(option)
        if key in seen:
            continue
        seen.add(key)
        alternatives.append(option)

    for option in _fallback_alternatives(
        direction=direction,
        from_city=from_city,
        to_city=to_city,
        travelers=travelers,
        fallback_departure=fallback_departure,
        anchor_departure=anchor_departure,
        anchor_arrival=anchor_arrival,
        excluded_modes={str(best_option.get("mode") or "")},
        source_name="fallback_candidate",
    ):
        if len(alternatives) >= 3:
            break
        key = _transport_option_key(option)
        if key in seen:
            continue
        seen.add(key)
        alternatives.append(option)

    return _leg_from_options(
        direction=direction,
        from_city=from_city,
        to_city=to_city,
        travelers=travelers,
        best_option=best_option,
        alternatives=alternatives,
        source="llm",
    )


def _build_fallback_leg(
    *,
    direction: str,
    from_city: str,
    to_city: str,
    travelers: int,
    trip_start: date,
    travel_days: int,
    outbound_departure_at: datetime | None,
    return_arrival_at: datetime | None,
) -> Dict[str, Any]:
    fallback_departure = _default_departure_datetime(direction, trip_start, travel_days, 240)
    anchor_departure = outbound_departure_at if direction == "outbound" else None
    anchor_arrival = return_arrival_at if direction == "inbound" else None
    best_option = _build_transport_option(
        source={
            "mode": "交通待确认",
            "from_terminal": f"{from_city}主要交通枢纽",
            "to_terminal": f"{to_city}主要交通枢纽",
            "reason": "大模型交通推荐暂不可用，需出行前核对实际班次和票价。",
        },
        direction=direction,
        from_city=from_city,
        to_city=to_city,
        travelers=travelers,
        fallback_departure=fallback_departure,
        anchor_departure=anchor_departure,
        anchor_arrival=anchor_arrival,
        default_mode="交通待确认",
        default_from_terminal=f"{from_city}主要交通枢纽",
        default_to_terminal=f"{to_city}主要交通枢纽",
        source_name="fallback",
    )
    best_option["recommended"] = True
    alternatives = _fallback_alternatives(
        direction=direction,
        from_city=from_city,
        to_city=to_city,
        travelers=travelers,
        fallback_departure=fallback_departure,
        anchor_departure=anchor_departure,
        anchor_arrival=anchor_arrival,
        excluded_modes=set(),
        source_name="fallback",
    )
    return _leg_from_options(
        direction=direction,
        from_city=from_city,
        to_city=to_city,
        travelers=travelers,
        best_option=best_option,
        alternatives=alternatives,
        source="fallback",
    )


def _build_transport_option(
    *,
    source: Dict[str, Any],
    direction: str,
    from_city: str,
    to_city: str,
    travelers: int,
    fallback_departure: datetime,
    fallback_duration: int | None = None,
    anchor_departure: datetime | None = None,
    anchor_arrival: datetime | None = None,
    default_mode: str = "交通待确认",
    default_from_terminal: str | None = None,
    default_to_terminal: str | None = None,
    source_name: str = "llm",
) -> Dict[str, Any]:
    source = source if isinstance(source, dict) else {}
    mode = _first_text(source, "mode", "transport_mode", "transportMode", "transportation", "type") or default_mode
    from_terminal = _first_text(
        source,
        "from_terminal",
        "fromTerminal",
        "origin_terminal",
        "originTerminal",
        "departure_terminal",
        "departureTerminal",
        "from_station",
        "fromStation",
        "origin_station",
        "originStation",
        "departure_station",
        "departureStation",
    ) or default_from_terminal or _terminal_for_mode(from_city, mode, is_origin=True)
    to_terminal = _first_text(
        source,
        "to_terminal",
        "toTerminal",
        "destination_terminal",
        "destinationTerminal",
        "arrival_terminal",
        "arrivalTerminal",
        "to_station",
        "toStation",
        "destination_station",
        "destinationStation",
        "arrival_station",
        "arrivalStation",
    ) or default_to_terminal or _terminal_for_mode(to_city, mode, is_origin=False)

    default_duration = fallback_duration if fallback_duration is not None else _default_duration_for_mode(mode)
    minimum_duration = 0 if default_duration <= 0 else 30
    duration_minutes = max(_safe_int(source.get("duration_minutes") or source.get("durationMinutes") or source.get("duration"), default_duration), minimum_duration)
    source_depart_at = _parse_datetime(source.get("departure_datetime") or source.get("departureDatetime") or source.get("departure_time"))
    source_arrive_at = _parse_datetime(source.get("arrival_datetime") or source.get("arrivalDatetime") or source.get("arrival_time"))

    if anchor_departure:
        depart_at = anchor_departure
        arrive_at = source_arrive_at if source_arrive_at and source_arrive_at > depart_at else depart_at + timedelta(minutes=duration_minutes)
    elif anchor_arrival:
        arrive_at = anchor_arrival
        depart_at = source_depart_at if source_depart_at and source_depart_at < arrive_at else arrive_at - timedelta(minutes=duration_minutes)
    else:
        depart_at = source_depart_at or fallback_departure
        arrive_at = source_arrive_at or (depart_at + timedelta(minutes=duration_minutes))
        if arrive_at < depart_at or (minimum_duration and arrive_at == depart_at):
            arrive_at = depart_at + timedelta(minutes=duration_minutes)

    duration_minutes = int((arrive_at - depart_at).total_seconds() // 60)
    if duration_minutes < minimum_duration:
        duration_minutes = minimum_duration
        arrive_at = depart_at + timedelta(minutes=duration_minutes)

    cost_per_person = max(
        _safe_int(
            source.get("cost_per_person")
            or source.get("costPerPerson")
            or source.get("price_per_person")
            or source.get("pricePerPerson")
            or source.get("fare_per_person")
            or source.get("farePerPerson")
            or source.get("ticket_price")
            or source.get("ticketPrice")
            or source.get("cost")
            or source.get("price"),
            0,
        ),
        0,
    )
    if not cost_per_person:
        cost_per_person = _default_cost_for_mode(mode, duration_minutes)
    total_cost = int(cost_per_person * max(travelers, 1))
    return {
        "mode": mode,
        "from_terminal": from_terminal,
        "to_terminal": to_terminal,
        "departure_datetime": _format_datetime(depart_at),
        "arrival_datetime": _format_datetime(arrive_at),
        "departure_time": depart_at.strftime("%H:%M"),
        "arrival_time": arrive_at.strftime("%H:%M"),
        "duration_minutes": duration_minutes,
        "duration_text": _format_duration(duration_minutes),
        "cost_per_person": cost_per_person,
        "total_cost": total_cost,
        "currency": "CNY",
        "estimated": True,
        "cost_pending": False,
        "source": source_name,
        "reason": str(source.get("reason") or source.get("note") or "").strip(),
        "recommended": bool(source.get("recommended") or source.get("is_best") or source.get("isBest")),
    }


def _leg_from_options(
    *,
    direction: str,
    from_city: str,
    to_city: str,
    travelers: int,
    best_option: Dict[str, Any],
    alternatives: list[Dict[str, Any]],
    source: str,
) -> Dict[str, Any]:
    total_cost = int(best_option.get("total_cost") or int(best_option.get("cost_per_person", 0) or 0) * max(travelers, 1))
    options = [dict(best_option), *[dict(item) for item in alternatives]]
    return {
        "direction": direction,
        "from": from_city,
        "to": to_city,
        "mode": str(best_option.get("mode") or "交通待确认"),
        "from_terminal": str(best_option.get("from_terminal") or from_city),
        "to_terminal": str(best_option.get("to_terminal") or to_city),
        "departure_datetime": best_option.get("departure_datetime"),
        "arrival_datetime": best_option.get("arrival_datetime"),
        "departure_time": best_option.get("departure_time"),
        "arrival_time": best_option.get("arrival_time"),
        "duration_minutes": int(best_option.get("duration_minutes") or 0),
        "duration_text": best_option.get("duration_text") or _format_duration(int(best_option.get("duration_minutes") or 0)),
        "distance_km": float(best_option.get("distance_km") or 0),
        "cost_per_person": int(best_option.get("cost_per_person") or 0),
        "total_cost": total_cost,
        "currency": "CNY",
        "estimated": True,
        "cost_pending": False,
        "source": source,
        "note": str(best_option.get("reason") or "由大模型根据出发地、目的地、预算和日期估算，建议出行前核对实时班次与票价。").strip(),
        "best_option": dict(best_option),
        "alternatives": [dict(item) for item in alternatives],
        "options": options,
    }


def _transport_option_sources(source: Dict[str, Any]) -> list[Dict[str, Any]]:
    items: list[Dict[str, Any]] = []
    for key in ("alternatives", "candidate_options", "candidateOptions", "candidates", "options"):
        value = source.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            items.append(value)
    return items


def _fallback_alternatives(
    *,
    direction: str,
    from_city: str,
    to_city: str,
    travelers: int,
    fallback_departure: datetime,
    anchor_departure: datetime | None,
    anchor_arrival: datetime | None,
    excluded_modes: set[str],
    source_name: str,
) -> list[Dict[str, Any]]:
    options = []
    for mode in ("飞机", "高铁/动车", "火车", "自驾"):
        if mode in excluded_modes:
            continue
        duration = _default_duration_for_mode(mode)
        option = _build_transport_option(
            source={
                "mode": mode,
                "from_terminal": _terminal_for_mode(from_city, mode, is_origin=True),
                "to_terminal": _terminal_for_mode(to_city, mode, is_origin=False),
                "duration_minutes": duration,
                "reason": "候选交通方式，需结合实时班次、票价和个人偏好确认。",
            },
            direction=direction,
            from_city=from_city,
            to_city=to_city,
            travelers=travelers,
            fallback_departure=fallback_departure,
            fallback_duration=duration,
            anchor_departure=anchor_departure,
            anchor_arrival=anchor_arrival,
            default_mode=mode,
            source_name=source_name,
        )
        options.append(option)
    return options


def _first_dict(*values: Any) -> Dict[str, Any] | None:
    for value in values:
        if isinstance(value, dict):
            return value
    return None


def _first_text(source: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            text = str(value).strip()
            if text:
                return text
    return ""


def _transport_option_key(option: Dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(option.get("mode") or "").strip().lower(),
        str(option.get("from_terminal") or "").strip().lower(),
        str(option.get("to_terminal") or "").strip().lower(),
        str(option.get("departure_datetime") or "").strip(),
    )


def _terminal_for_mode(city: str, mode: str, *, is_origin: bool) -> str:
    text = mode.lower()
    if "飞机" in mode or "航班" in mode or "flight" in text:
        return f"{city}主要机场"
    if "高铁" in mode or "动车" in mode:
        return f"{city}主要高铁站"
    if "火车" in mode or "普铁" in mode:
        return f"{city}主要火车站"
    if "汽车" in mode or "大巴" in mode or "客运" in mode:
        return f"{city}主要客运站"
    if "自驾" in mode:
        return city
    return f"{city}主要交通枢纽"


def _default_duration_for_mode(mode: str) -> int:
    text = mode.lower()
    for key, duration in DEFAULT_MODE_DURATIONS.items():
        if key in mode or key.lower() in text:
            return duration
    return 240


def _estimate_mode_time_cost(distance_km: float, route_duration_minutes: int) -> Tuple[str, int, int]:
    for threshold, mode, cost_fn in TRANSPORT_MODE_RULES:
        if distance_km <= threshold:
            if distance_km <= 80:
                minutes = route_duration_minutes or max(45, int(distance_km) + 20)
            elif distance_km <= 650:
                minutes = max(75, int(40 + distance_km * 0.48))
            elif distance_km <= 1200:
                minutes = max(150, int(70 + distance_km * 0.52))
            else:
                minutes = max(180, int(150 + distance_km * 0.08))
            return mode, minutes, _round_money(cost_fn(distance_km))
    return "飞机/高铁", 240, _round_money(280 + distance_km * 0.62)


def _default_departure_datetime(direction: str, trip_start: date, travel_days: int, duration_minutes: int) -> datetime:
    if direction == "outbound":
        departure_time = time(8, 0) if duration_minutes <= 300 else time(7, 30)
        return datetime.combine(trip_start, departure_time)
    return_date = trip_start + timedelta(days=travel_days - 1)
    if duration_minutes <= 150:
        departure_time = time(17, 0)
    elif duration_minutes <= 360:
        departure_time = time(16, 0)
    else:
        departure_time = time(15, 0)
    return datetime.combine(return_date, departure_time)


def _default_cost_for_mode(mode: str, duration_minutes: int) -> int:
    text = mode.lower()
    if "飞机" in mode or "航班" in mode or "flight" in text:
        return _round_money(max(450, duration_minutes * 1.4))
    if "高铁" in mode or "动车" in mode or "火车" in mode:
        return _round_money(max(80, duration_minutes * 0.9))
    if "自驾" in mode:
        return _round_money(max(120, duration_minutes * 0.8))
    return _round_money(max(60, duration_minutes * 0.55))


def _round_money(value: float) -> int:
    return int(round(value / 10.0) * 10)


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


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _format_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        matched = re.search(r"\d+(?:\.\d+)?", str(value or ""))
        return int(float(matched.group())) if matched else default
    except Exception:
        return default


def _extract_json(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {}


def _message_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        return "\n".join(str(item.get("text") or item.get("content") or item) if isinstance(item, dict) else str(item) for item in content)
    return str(content or "")
