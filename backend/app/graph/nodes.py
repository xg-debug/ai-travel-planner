import logging
from typing import Any, Dict

from app.agents.shared import build_local_summary
from app.domain import travel_domain_service
from app.orchestration.task_models import build_task_result
from app.orchestration.task_router import complete_task
from app.services.budget_service import estimate_budget
from app.services.risk_notice_service import risk_notice_service
from app.services.scoring_service import scoring_service
from app.services.weather_impact_service import weather_impact_service

logger = logging.getLogger(__name__)


def weather_tool_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """天气工具步骤：直接取确定性天气数据，不单独建 agent。"""
    logger.info("Fetching weather via tool for %s", state["city"])

    city = state["city"]
    days = state["days"]

    try:
        weather_data = travel_domain_service.get_weather(city, days)
    except Exception as exc:
        logger.warning("Weather fetch failed city=%s error=%s", city, exc)
        weather_data = {
            "city": city,
            "report_time": "",
            "forecast": [
                {
                    "date": "",
                    "condition": "未知",
                    "day_condition": "未知",
                    "night_condition": "未知",
                    "temperature": {"min": 0, "max": 0, "avg": 0},
                    "humidity": 0,
                    "wind_speed": 0,
                    "icon": "unknown",
                }
                for _ in range(days)
            ],
        }
    weather_impacts = weather_impact_service.build_impacts(weather_data, state.get("start_date"), days)

    logger.info("Weather data fetched: %s days", len(weather_data.get("forecast", [])))
    return {"weather_data": weather_data, "weather_impacts": weather_impacts}


def scoring_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """候选评分排序步骤。"""
    logger.info("Scoring candidates for %s", state["city"])
    context = {
        "city": state.get("city", ""),
        "preferences": state.get("preferences", []) or [],
        "budget": state.get("budget", "中等"),
        "budget_amount": state.get("budget_amount") or 0,
        "travelers": state.get("travelers", 1) or 1,
        "days": state.get("days", 1) or 1,
        "weather_impacts": state.get("weather_impacts", []) or [],
    }
    attractions = scoring_service.score_attractions(state.get("attraction_candidates", []) or [], context)
    foods = scoring_service.score_foods(state.get("food_candidates", []) or [], context)
    hotels = scoring_service.score_hotels(state.get("hotel_options", []) or [], context)
    return {
        "scored_attractions": attractions,
        "scored_foods": foods,
        "scored_hotels": hotels,
        "attraction_candidates": attractions,
        "food_candidates": foods,
        "hotel_options": hotels,
        **complete_task(
            state,
            "scoring",
            build_task_result(
                output={
                    "attractions": len(attractions),
                    "foods": len(foods),
                    "hotels": len(hotels),
                },
                metrics={
                    "top_attraction_score": attractions[0].get("score", 0) if attractions else 0,
                    "top_food_score": foods[0].get("score", 0) if foods else 0,
                    "top_hotel_score": hotels[0].get("score", 0) if hotels else 0,
                },
                summary="已完成候选评分排序。",
            ),
        ),
    }


def workflow_error_node(state: Dict[str, Any]) -> Dict[str, Any]:
    pending_steps = [task.get("step", "") for task in (state.get("tasks", []) or []) if task.get("status") == "pending"]
    raise RuntimeError(f"任务工作流阻塞，存在未完成但不可调度的任务: {pending_steps}")


def budget_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """预算估算步骤。"""
    logger.info("Estimating budget for %s days trip", state["days"])

    plan = state.get("plan", [])
    travelers = state.get("travelers", 1)
    budget_level = state.get("budget", "中等")

    estimated_budget = estimate_budget(plan, travelers, budget_level)
    if state.get("budget_amount"):
        estimated_budget["requested_total"] = int(float(state.get("budget_amount") or 0))
        estimated_budget["is_over_budget"] = int(estimated_budget.get("total") or 0) > estimated_budget["requested_total"]
    logger.info("Estimated budget: %s %s", estimated_budget.get("total"), estimated_budget.get("currency"))
    daily_budgets = estimated_budget.get("daily_budgets", [])
    enriched_plan = []
    for index, day in enumerate(plan or []):
        next_day = dict(day)
        if index < len(daily_budgets):
            next_day["budget"] = daily_budgets[index]
        enriched_plan.append(next_day)
    return {"plan": enriched_plan or plan, "estimated_budget": estimated_budget, "daily_budgets": daily_budgets}


def risk_notice_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """避坑提醒步骤。"""
    notices = risk_notice_service.build_notices(state)
    return {"risk_notices": notices}


def summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """行程总结步骤。"""
    logger.info("Generating final trip summary")
    final_output = build_local_summary(state)
    logger.info("Summary generated locally")
    return {"final_output": final_output}
