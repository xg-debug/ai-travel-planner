import logging
from typing import Any, Dict

from app.agents.shared import build_local_summary
from app.domain import travel_domain_service
from app.services.budget_service import estimate_budget

logger = logging.getLogger(__name__)


def weather_tool_step(state: Dict[str, Any]) -> Dict[str, Any]:
    """天气工具步骤：直接取确定性天气数据，不单独建 agent。"""
    logger.info("Fetching weather via tool for %s", state["city"])

    city = state["city"]
    days = state["days"]

    weather_data = travel_domain_service.get_weather(city, days)

    logger.info("Weather data fetched: %s days", len(weather_data.get("forecast", [])))
    return {"weather_data": weather_data}


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
    logger.info("Estimated budget: %s %s", estimated_budget.get("total"), estimated_budget.get("currency"))
    return {"estimated_budget": estimated_budget}


def summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """行程总结步骤。"""
    logger.info("Generating final trip summary")
    final_output = build_local_summary(state)
    logger.info("Summary generated locally")
    return {"final_output": final_output}
