from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.trip_planning.harness import EventSink
from app.trip_planning.errors import classify_planning_error
from app.trip_planning.itinerary import summary_node
from app.trip_planning.nodes import (
    _fallback_itinerary,
    finalizer_node,
    planner_node,
    replanner_node,
)
from app.trip_planning.tool_executor import TripPlanningToolbox, finalize_budget_and_risk

logger = logging.getLogger(__name__)


ACTION_PROGRESS = {
    "get_weather": ("weather_lookup", "目的地天气与出行条件"),
    "search_attractions": ("attraction_search", "真实景点与旅行体验"),
    "search_foods": ("food_search", "沿途餐厅与本地风味"),
    "recommend_hotels": ("hotel_search", "住宿区域与参考价"),
    "plan_transport": ("transport_planning", "往返与城市内交通"),
}


class PlanExecuteReplanAgent:
    """Bounded agent loop using real tools and an observable harness.

    The LLM plans and reviews tool actions. The executor owns deterministic API
    calls, while this class enforces a small iteration budget so a flaky tool or
    malformed model response cannot leave a client waiting indefinitely.
    """

    def __init__(self, max_iterations: int = 2) -> None:
        self._max_iterations = max(1, max_iterations)
        self._toolbox = TripPlanningToolbox()

    def run(self, state: Dict[str, Any], emit: EventSink | None = None) -> Dict[str, Any]:
        working = {
            **dict(state),
            "iteration": 0,
            "max_iterations": self._max_iterations,
            "executed_actions": [],
            "tool_results": dict(state.get("tool_results") or {}),
        }

        try:
            working.update(planner_node(working))
        except Exception as exc:
            logger.warning("Planner reasoning failed; using safe action plan: %s", exc)
            self._record_fallback(working, exc, emit)
            working.update(self._fallback_plan(working))

        for iteration in range(self._max_iterations):
            actions = list(working.get("next_actions") or [])
            if not actions:
                break
            self._execute_actions(working, actions, emit)
            working["iteration"] = iteration + 1

            if iteration >= self._max_iterations - 1:
                break
            if emit:
                emit("itinerary_review", "正在检查工具结果是否足够生成可靠行程")
            try:
                decision = replanner_node(working)
                working.update(decision)
            except Exception as exc:
                logger.warning("Replanner failed; finalizing with current evidence: %s", exc)
                break
            if str(working.get("replanner_decision") or "final") == "final":
                break
            if str(working.get("replanner_decision")) == "replan":
                try:
                    working.update(planner_node(working))
                except Exception:
                    break

        if emit:
            emit("itinerary_synthesis", "正在把真实地点、天气和预算编排成每日行程")
        try:
            working.update(finalizer_node(working))
        except Exception as exc:
            logger.warning("Finalizer failed; using deterministic itinerary fallback: %s", exc)
            self._record_fallback(working, exc, emit)
            working["plan"] = _fallback_itinerary(working)
            working.update(finalize_budget_and_risk(working))
            working.update(summary_node(working))

        if not any(day.get("activities") for day in working.get("plan") or []):
            raise RuntimeError("真实地点数据不足，暂时无法生成可用行程")

        from app.services.map_route_service import enrich_itinerary_routes
        if emit:
            emit("transport_planning", "正在通过高德 MCP 核对每日交通路线")
        enrich_itinerary_routes(working)

        if emit:
            emit("itinerary_review", "已检查地点真实性、重复安排和每日活动密度")
            emit("budget_estimation", "已按人数、间夜和活动参考价完成预算估算")
            emit("risk_notices", "已结合天气与路线生成出行提醒")
        working["agent_run"] = {
            **dict(working.get("agent_run") or {}),
            "planner": "plan_execute_replan",
            "iterations": int(working.get("iteration") or 1),
            "executed_actions": list(working.get("executed_actions") or []),
        }
        return working

    @staticmethod
    def _record_fallback(state: Dict[str, Any], error: Exception, emit: EventSink | None) -> None:
        classified = classify_planning_error(error)
        reason = "AI 模型服务余额不足" if classified["code"] == "LLM_INSUFFICIENT_BALANCE" else "AI 模型服务暂时不可用"
        message = f"{reason}，本次提供基于真实地图数据的基础行程，尚未完成完整 AI 规划。"
        warnings = state.setdefault("planning_warnings", [])
        if message not in warnings:
            warnings.append(message)
            if emit:
                emit("model_fallback", message, {"degraded": True, "code": classified["code"]})

    def _execute_actions(
        self,
        state: Dict[str, Any],
        actions: List[Dict[str, Any]],
        emit: EventSink | None,
    ) -> None:
        order = {"get_weather": 0, "search_attractions": 1, "recommend_hotels": 2, "search_foods": 3, "plan_transport": 4}
        for action in sorted(actions, key=lambda item: order.get((item or {}).get("name"), 5)):
            name = str((action or {}).get("name") or "").strip()
            if name not in ACTION_PROGRESS:
                continue
            args = action.get("args") if isinstance(action.get("args"), dict) else {}
            step, label = ACTION_PROGRESS[name]
            if emit:
                emit(step, f"正在查询{label}", {"action": name})
            try:
                update = self._toolbox.execute_one(name, args, state)
                self._merge_update(state, update)
                state.setdefault("tool_results", {})[name] = update
                if emit:
                    emit(step, f"已获得{label}", {"action": name, "ok": True})
            except Exception as exc:
                logger.warning("Agent action failed name=%s error=%s", name, exc)
                state.setdefault("tool_results", {})[name] = {"error": str(exc)}
                if emit:
                    emit(step, f"{label}暂时不可用，继续使用已有信息", {"action": name, "ok": False})
            state.setdefault("executed_actions", []).append(name)
        state["next_actions"] = []

    @staticmethod
    def _merge_update(target: Dict[str, Any], update: Dict[str, Any]) -> None:
        for key, value in (update or {}).items():
            if value not in (None, "", [], {}):
                target[key] = value

    @staticmethod
    def _fallback_plan(state: Dict[str, Any]) -> Dict[str, Any]:
        city = str(state.get("city") or "")
        days = int(state.get("days") or 1)
        actions = [
            {"name": "get_weather", "args": {"city": city, "days": days}},
            {"name": "search_attractions", "args": {"queries": [f"{city}热门景点", f"{city}特色街区", f"{city}自然风光"]}},
            {"name": "search_foods", "args": {"queries": [f"{city}本地特色美食", f"{city}老字号餐厅"]}},
            {"name": "recommend_hotels", "args": {"areas": [f"{city}核心游览区"], "count": 4}},
            {"name": "plan_transport", "args": {}},
        ]
        return {
            "planning_brief": {
                "travel_style": "、".join(state.get("preferences") or []) or "城市经典游",
                "area_strategy": "每天围绕一个核心片区组织路线，减少折返。",
                "hotel_strategy": "住宿靠近主要游览区与公共交通。",
                "budget_strategy": "按用户总预算控制住宿和活动费用。",
            },
            "action_plan": {"actions": actions},
            "next_actions": actions,
        }


# One execute pass is the production default. The class still supports an
# explicit second pass for experiments, while normal requests avoid repeating
# all external searches when evidence is already sufficient for finalization.
plan_execute_replan_agent = PlanExecuteReplanAgent(max_iterations=1)
