import logging
from typing import Any, Dict

from app.agents.shared import build_local_summary
from app.services.amap_service import get_weather_forecast
from app.services.budget_service import estimate_budget

logger = logging.getLogger(__name__)


def weather_tool_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """天气工具步骤：直接取确定性天气数据，不单独建 agent。"""
    logger.info("Fetching weather via tool for %s", state["city"])

    city = state["city"]
    days = state["days"]

    try:
        weather_data = get_weather_forecast(city, days)
    except Exception as exc:
        logger.error("Error fetching weather: %s", exc)
        weather_data = {"city": city, "report_time": "", "forecast": []}

    logger.info("Weather data fetched: %s days", len(weather_data.get("forecast", [])))
    return {"weather_data": weather_data}


def budget_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """预算估算步骤。"""
    logger.info("Estimating budget for %s days trip", state["days"])

    plan = state.get("plan", [])
    travelers = state.get("travelers", 1)
    budget_level = state.get("budget", "中等")

    estimated_budget = estimate_budget(plan, travelers, budget_level)
    logger.info("Estimated budget: %s %s", estimated_budget.get("total"), estimated_budget.get("currency"))
    return {"estimated_budget": estimated_budget}


def summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """行程总结步骤。"""
    logger.info("Generating final trip summary")

    try:
        final_output = build_local_summary(state)
        logger.info("Summary generated locally")
        return {"final_output": final_output}
    except Exception as exc:
        logger.error("Error in summary_node: %s", exc)
        return {"final_output": f"# {state['city']} {state['days']}天旅行计划\n请稍后重试以获取完整总结。"}
