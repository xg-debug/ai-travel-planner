from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.core.llm import invoke_llm_with_fallback
from app.trip_planning.graph_state import TripPlanningGraphState
from app.trip_planning.itinerary import normalize_itinerary, summary_node
from app.trip_planning.prompts import build_finalizer_prompt, build_planner_prompt, build_replanner_prompt
from app.trip_planning.tool_executor import TripPlanningToolbox, finalize_budget_and_risk
from app.trip_planning.utils import extract_json_block

logger = logging.getLogger(__name__)

toolbox = TripPlanningToolbox()


def planner_node(state: TripPlanningGraphState) -> Dict[str, Any]:
    response = invoke_llm_with_fallback(
        build_planner_prompt(dict(state)),
        temperature=0.25,
        max_tokens=1800,
        request_timeout=35,
    )
    parsed = extract_json_block(getattr(response, "content", response)) or {}
    if not isinstance(parsed, dict):
        parsed = {}
    actions = _normalize_actions(parsed.get("actions"), state)
    return {
        "planning_brief": parsed.get("planning_brief") if isinstance(parsed.get("planning_brief"), dict) else _fallback_brief(state),
        "action_plan": {"actions": actions},
        "next_actions": actions,
        "iteration": int(state.get("iteration") or 0),
        "max_iterations": int(state.get("max_iterations") or 2),
    }


def executor_node(state: TripPlanningGraphState) -> Dict[str, Any]:
    actions = list(state.get("next_actions") or [])
    updates = toolbox.execute(dict(state), actions)
    executed = list(state.get("executed_actions") or [])
    executed.extend(str(action.get("name") or "") for action in actions if isinstance(action, dict))
    return {
        **updates,
        "executed_actions": [item for item in executed if item],
        "next_actions": [],
    }


def replanner_node(state: TripPlanningGraphState) -> Dict[str, Any]:
    iteration = int(state.get("iteration") or 0) + 1
    max_iterations = int(state.get("max_iterations") or 2)
    if iteration >= max_iterations and _has_minimum_inputs(state):
        return {
            "iteration": iteration,
            "replanner_decision": "final",
            "replanner_reason": "达到闭环上限，现有工具结果已足够生成行程。",
            "next_actions": [],
        }

    response = invoke_llm_with_fallback(
        build_replanner_prompt({**dict(state), "iteration": iteration, "max_iterations": max_iterations}),
        temperature=0.15,
        max_tokens=1200,
        request_timeout=30,
    )
    parsed = extract_json_block(getattr(response, "content", response)) or {}
    if not isinstance(parsed, dict):
        parsed = {}
    decision = str(parsed.get("decision") or "").strip().lower()
    if decision not in {"continue", "replan", "final"}:
        decision = "final" if _has_minimum_inputs(state) else "continue"
    next_actions = _normalize_actions(parsed.get("next_actions"), state) if decision == "continue" else []
    if decision == "continue" and not next_actions:
        decision = "final" if _has_minimum_inputs(state) else "replan"
    return {
        "iteration": iteration,
        "replanner_decision": decision,
        "replanner_reason": str(parsed.get("reason") or ""),
        "next_actions": next_actions,
        "replan_request": str(parsed.get("replan_request") or ""),
    }


def finalizer_node(state: TripPlanningGraphState) -> Dict[str, Any]:
    response = invoke_llm_with_fallback(
        build_finalizer_prompt(dict(state)),
        temperature=0.25,
        max_tokens=_finalizer_tokens(state),
        request_timeout=90,
    )
    parsed = extract_json_block(getattr(response, "content", response)) or {}
    itinerary = parsed.get("itinerary") if isinstance(parsed, dict) else []
    plan = normalize_itinerary(itinerary or [], dict(state))
    plan = _attach_consistent_hotels(plan, list(state.get("hotel_options") or []))
    final_output = str(parsed.get("final_output") or "") if isinstance(parsed, dict) else ""
    if not any(day.get("activities") for day in plan):
        plan = _fallback_itinerary(dict(state))
        final_output = ""

    next_state = {**dict(state), "plan": plan, "final_output": final_output}
    budget_risk = finalize_budget_and_risk(next_state)
    next_state.update(budget_risk)
    if not next_state.get("final_output"):
        next_state.update(summary_node(next_state))
    next_state["quality_score"] = _quality_score(next_state)
    return {
        "plan": next_state.get("plan", plan),
        "final_output": next_state.get("final_output", ""),
        "estimated_budget": next_state.get("estimated_budget", {}),
        "daily_budgets": next_state.get("daily_budgets", []),
        "risk_notices": next_state.get("risk_notices", []),
        "intercity_transport": next_state.get("intercity_transport", state.get("intercity_transport", {})),
        "quality_score": next_state.get("quality_score", {}),
    }


def route_after_replanner(state: TripPlanningGraphState) -> str:
    decision = str(state.get("replanner_decision") or "final")
    if decision == "continue":
        return "executor"
    if decision == "replan":
        return "planner"
    return "finalizer"


def _normalize_actions(value: Any, state: Dict[str, Any]) -> List[Dict[str, Any]]:
    allowed = {"get_weather", "search_attractions", "search_foods", "recommend_hotels", "plan_transport"}
    actions: List[Dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name not in allowed:
            continue
        args = item.get("args") if isinstance(item.get("args"), dict) else {}
        actions.append({"name": name, "args": args or {}})
    if actions:
        return actions
    city = str(state.get("city") or "").strip()
    days = int(state.get("days") or 1)
    return [
        {"name": "get_weather", "args": {"city": city, "days": days}},
        {
            "name": "search_attractions",
            "args": {"queries": [f"{city}热门景点", f"{city}特色街区", f"{city}自然风光", f"{city}夜景地标"]},
        },
        {"name": "search_foods", "args": {"queries": [f"{city}本地特色美食", f"{city}老字号餐厅", f"{city}美食街"]}},
        {"name": "recommend_hotels", "args": {"areas": [f"{city}核心游览区"], "count": 5}},
        {"name": "plan_transport", "args": {}},
    ]


def _fallback_brief(state: Dict[str, Any]) -> Dict[str, Any]:
    preference_text = "、".join(state.get("preferences") or []) or "城市经典游"
    return {
        "travel_style": preference_text,
        "user_priorities": state.get("preferences") or [],
        "area_strategy": "按每天一个核心片区组织路线，减少折返。",
        "hotel_strategy": "住宿靠近主要游览区和公共交通。",
        "budget_strategy": "按用户预算和住宿档位控制总额。",
    }


def _has_minimum_inputs(state: Dict[str, Any]) -> bool:
    days = int(state.get("days") or 1)
    return (
        len(state.get("attraction_candidates", []) or []) >= max(4, days * 2)
        and len(state.get("food_candidates", []) or []) >= max(2, days)
        and len(state.get("hotel_options", []) or []) >= 1
    )


def _finalizer_tokens(state: Dict[str, Any]) -> int:
    days = int(state.get("days") or 1)
    return min(5000, max(2200, days * 850))


def _attach_consistent_hotels(plan: List[Dict[str, Any]], hotels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not hotels:
        return plan
    primary = hotels[0]
    for day in plan:
        hotel = day.get("hotel_recommendation") or {}
        if not hotel.get("name"):
            day["hotel_recommendation"] = _hotel_for_day(primary)
            continue
        matched = next((item for item in hotels if str(item.get("name")) == str(hotel.get("name"))), None)
        if matched:
            day["hotel_recommendation"] = {**_hotel_for_day(matched), **hotel}
            day["hotel_recommendation"]["price_is_estimated"] = True
    return plan


def _hotel_for_day(hotel: Dict[str, Any]) -> Dict[str, Any]:
    lat = float(hotel.get("lat") or 0)
    lng = float(hotel.get("lng") or 0)
    result = {
        "name": hotel.get("name", ""),
        "price_estimate": hotel.get("price_estimate") or hotel.get("price") or "",
        "price_is_estimated": True,
        "address": hotel.get("address", ""),
        "reason": hotel.get("reason", ""),
        "source": hotel.get("source", "llm_hotel"),
        "source_id": hotel.get("id", ""),
    }
    if lat and lng:
        result["coordinates"] = {"lat": lat, "lng": lng}
    return result


def _fallback_itinerary(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    days = int(state.get("days") or 1)
    attractions = list(state.get("attraction_candidates") or [])
    foods = list(state.get("food_candidates") or [])
    hotels = list(state.get("hotel_options") or [])
    plan: List[Dict[str, Any]] = []
    for index in range(days):
        day_attractions = attractions[index * 2 : index * 2 + 2] or attractions[:2]
        day_foods = foods[index * 2 : index * 2 + 2] or foods[:2]
        activities: List[Dict[str, Any]] = []
        if day_attractions:
            activities.append(_activity_from_candidate(day_attractions[0], "09:30-11:30", "景点游览"))
        if day_foods:
            activities.append(_activity_from_candidate(day_foods[0], "12:00-13:15", "美食餐饮", "午餐"))
        if len(day_attractions) > 1:
            activities.append(_activity_from_candidate(day_attractions[1], "14:30-16:30", "景点游览"))
        if len(day_foods) > 1:
            activities.append(_activity_from_candidate(day_foods[1], "18:00-19:30", "美食餐饮", "晚餐"))
        plan.append(
            {
                "day": index + 1,
                "date": None,
                "theme": f"{state.get('city', '')}第{index + 1}天",
                "summary": "根据可用工具结果生成的精简可执行安排。",
                "weather_advice": "",
                "hotel_recommendation": _hotel_for_day(hotels[min(index, len(hotels) - 1)]) if hotels else {},
                "activities": activities,
            }
        )
    return normalize_itinerary(plan, state)


def _activity_from_candidate(item: Dict[str, Any], time: str, activity_type: str, prefix: str = "") -> Dict[str, Any]:
    name = str(item.get("name") or "").strip()
    title = f"{prefix}：{name}" if prefix else name
    lat = float(item.get("lat") or 0)
    lng = float(item.get("lng") or 0)
    activity: Dict[str, Any] = {
        "time": time,
        "title": title,
        "description": item.get("description") or item.get("address") or "",
        "type": activity_type,
        "location": name,
        "duration": 90,
        "cost_estimate": 0,
        "ticket_price": 0,
        "tips": "",
        "transportation": "建议结合实时地图导航。",
        "source": item.get("source", ""),
        "source_id": item.get("id", ""),
    }
    if lat and lng:
        activity["coordinates"] = {"lat": lat, "lng": lng}
    return activity


def _quality_score(state: Dict[str, Any]) -> Dict[str, Any]:
    plan = state.get("plan", []) or []
    locations = [
        str(activity.get("location") or "").strip()
        for day in plan
        for activity in (day.get("activities") or [])
        if str(activity.get("location") or "").strip()
    ]
    unique_ratio = len(set(locations)) / max(len(locations), 1)
    return {
        "score": round(70 + unique_ratio * 25, 1),
        "unique_location_ratio": round(unique_ratio, 2),
        "review": "Plan-Execute-Replan 工作流已完成基础质量检查。",
    }
