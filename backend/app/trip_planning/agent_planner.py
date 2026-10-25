from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List

from app.trip_planning.harness import EventSink
from app.trip_planning.errors import classify_planning_error
from app.trip_planning.itinerary import summary_node
from app.trip_planning.quality import audit_plan
from app.trip_planning.budget import budget_node
from app.trip_planning.trace import record_event, summarize_tool_result
from app.trip_planning.nodes import (
    _fallback_itinerary,
    finalizer_node,
    planner_node,
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
    """Bounded Plan-Execute with deterministic, targeted candidate repair."""

    def __init__(self, max_iterations: int = 2) -> None:
        self._max_iterations = max(1, max_iterations)
        self._toolbox = TripPlanningToolbox()

    def run(
        self,
        state: Dict[str, Any],
        emit: EventSink | None = None,
        checkpoint: Callable[[str, Dict[str, Any]], None] | None = None,
        resume: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        working = dict(resume) if resume else {
            **dict(state), "iteration": 0, "max_iterations": self._max_iterations,
            "executed_actions": [], "tool_results": dict(state.get("tool_results") or {}),
        }

        def save(phase: str) -> None:
            working["_phase"] = phase
            if checkpoint:
                checkpoint(phase, dict(working))

        phase = str(working.get("_phase") or "new")
        if phase == "new":
            try:
                working.update(planner_node(working))
            except Exception as exc:
                logger.warning("Planner reasoning failed; using safe action plan: %s", exc)
                self._record_fallback(working, exc, emit)
                working.update(self._fallback_plan(working))
            record_event("decision", "initial_plan", "completed", output_summary={
                "actions": [item.get("name") for item in working.get("next_actions") or []],
                "fallback": bool(working.get("_model_unavailable")),
            })
            save("planned")
            phase = "planned"

        if phase in {"planned", "searching"}:
            self._execute_actions(working, list(working.get("next_actions") or []), emit, save)
            working["iteration"] = 1
            save("searched")
            phase = "searched"

        if phase == "searched":
            working["budget_envelope"] = self._budget_envelope(working)
            actions = self._targeted_actions(working) if self._max_iterations > 1 else []
            if actions:
                record_event("decision", "targeted_repair", "completed", output_summary={"actions": [item.get("name") for item in actions]})
                if emit:
                    emit("itinerary_review", "候选数据不足，正在定向补查")
                working["next_actions"] = actions
                save("repairing")
                phase = "repairing"

        if phase == "repairing":
            self._execute_actions(working, list(working.get("next_actions") or []), emit, save)
            working["iteration"] = 2
            working["budget_envelope"] = self._budget_envelope(working)
            save("researched")
            phase = "researched"

        if phase in {"searched", "researched"}:
            if emit:
                emit("itinerary_synthesis", "正在把真实地点、天气和预算编排成每日行程")
            if working.get("_model_unavailable"):
                working["plan"] = _fallback_itinerary(working)
                working.update(finalize_budget_and_risk(working))
                working.update(summary_node(working))
            else:
                try:
                    working.update(finalizer_node(working))
                except Exception as exc:
                    logger.warning("Finalizer failed; using deterministic itinerary fallback: %s", exc)
                    self._record_fallback(working, exc, emit)
                    working["plan"] = _fallback_itinerary(working)
                    working.update(finalize_budget_and_risk(working))
                    working.update(summary_node(working))
            save("finalized")
            phase = "finalized"

        if phase == "finalized":
            self._repair_budget(working, emit)
            save("budget_checked")
            phase = "budget_checked"

        if not any(day.get("activities") for day in working.get("plan") or []):
            raise RuntimeError("真实地点数据不足，暂时无法生成可用行程")

        if phase == "budget_checked":
            from app.services.map_route_service import enrich_itinerary_routes
            if emit:
                emit("transport_planning", "正在通过高德 MCP 核对每日交通路线")
            route_started = time.perf_counter()
            try:
                enrich_itinerary_routes(working)
                routes = [(day.get("map_route") or {}) for day in working.get("plan") or []]
                record_event("tool", "enrich_itinerary_routes", "completed", provider="amap_mcp",
                             duration_ms=round((time.perf_counter() - route_started) * 1000),
                             output_summary={"days": len(routes), "legs": sum(len(route.get("legs") or []) for route in routes),
                                             "partial_days": sum(bool(route.get("partial")) for route in routes)})
            except Exception as exc:
                record_event("tool", "enrich_itinerary_routes", "failed", provider="amap_mcp",
                             duration_ms=round((time.perf_counter() - route_started) * 1000),
                             error_code=type(exc).__name__)
                raise
            working.update(budget_node(working))
            record_event("decision", "budget_final", "completed", output_summary={
                "target": working.get("budget_amount"), "estimated": (working.get("estimated_budget") or {}).get("total"),
            })
            save("routed")

        quality = audit_plan(working)
        record_event("decision", "quality_audit", "completed", output_summary={
            "score": quality.get("score"), "verified_attractions": quality.get("verified_attraction_count"),
            "issue_count": len(quality.get("issues") or []),
        })
        if quality["verified_attraction_count"] == 0:
            raise RuntimeError("真实地点数据不足，无法生成可信行程，请稍后重试")
        working["quality_score"] = quality
        warnings = working.setdefault("planning_warnings", [])
        for issue in quality["issues"]:
            if issue not in warnings:
                warnings.append(issue)

        if emit:
            emit("itinerary_review", "已检查地点、每日安排与路线，待核对项目已标注" if quality["issues"] else "地点、每日安排与路线已通过基础检查")
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
    def _budget_envelope(state: Dict[str, Any]) -> Dict[str, Any]:
        target = max(0, int(state.get("budget_amount") or 0))
        if not target:
            return {}
        transport = state.get("intercity_transport") or {}
        fixed_transport = max(0, int(transport.get("total_cost") or 0))
        nights = max(0, int(state.get("days") or 1) - 1)
        rooms = max(1, (int(state.get("travelers") or 1) + 1) // 2)
        remaining = max(0, target - fixed_transport)
        return {
            "target_total": target,
            "known_intercity_transport": fixed_transport,
            "remaining_after_intercity": remaining,
            "hotel_reference_per_room_night": round(remaining * 0.4 / (rooms * nights)) if nights else 0,
            "fixed_cost_exceeds_target": fixed_transport >= target,
        }

    @staticmethod
    def _targeted_actions(state: Dict[str, Any]) -> List[Dict[str, Any]]:
        city = str(state.get("city") or "")
        days = max(1, int(state.get("days") or 1))
        actions = []
        if len(state.get("attraction_candidates") or []) < days * 2:
            actions.append({"name": "search_attractions", "args": {"queries": [f"{city}特色景点", f"{city}适合{days}日游的街区与自然景点"]}})
        if not state.get("hotel_options") and days > 1:
            actions.append({"name": "recommend_hotels", "args": {"areas": [f"{city}主要景点附近"], "count": 5}})
        if len(state.get("food_candidates") or []) < days:
            actions.append({"name": "search_foods", "args": {"queries": [f"{city}景点附近本地餐厅"]}})
        return actions

    @staticmethod
    def _repair_budget(state: Dict[str, Any], emit: EventSink | None) -> None:
        budget = state.get("estimated_budget") or {}
        target = int(state.get("budget_amount") or 0)
        total = int(budget.get("total") or 0)
        if target <= 0 or total <= target:
            return
        fixed_transport = int((state.get("intercity_transport") or {}).get("total_cost") or 0)
        if not state.get("_model_unavailable") and fixed_transport < target and total > target * 1.1:
            record_event("decision", "budget_repair", "started", output_summary={"target": target, "estimated": total})
            if emit:
                emit("budget_estimation", "预算超出目标，正在尝试调整可替换项目")
            state["budget_repair_instruction"] = (
                f"当前估算 {total} 元，用户目标 {target} 元。保留真实地点与用户偏好，"
                "仅调整未锁定的酒店、餐饮和付费活动；不要虚构低价。"
            )
            try:
                revised = finalizer_node(state)
                if int((revised.get("estimated_budget") or {}).get("total") or 0) < total:
                    state.update(revised)
                record_event("decision", "budget_repair", "completed", output_summary={
                    "before": total, "after": (state.get("estimated_budget") or {}).get("total"),
                })
            except Exception:
                logger.exception("Budget repair synthesis failed; keeping first itinerary")
                record_event("decision", "budget_repair", "failed", error_code="FINALIZER_FAILED")
        final_total = int((state.get("estimated_budget") or {}).get("total") or total)
        if final_total > target:
            state.setdefault("planning_warnings", []).append(f"行程估算约 {final_total} 元，超过目标预算 {target} 元；请核对参考价格或调整可选项目。")

    @staticmethod
    def _record_fallback(state: Dict[str, Any], error: Exception, emit: EventSink | None) -> None:
        classified = classify_planning_error(error)
        if classified["code"] in {"LLM_NOT_CONFIGURED", "LLM_INVALID_API_KEY", "LLM_INSUFFICIENT_BALANCE", "LLM_ALL_PROVIDERS_FAILED"}:
            state["_model_unavailable"] = True
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
        save: Callable[[str], None] | None = None,
    ) -> None:
        order = {"get_weather": 0, "search_attractions": 1, "recommend_hotels": 2, "search_foods": 3, "plan_transport": 4}
        remaining = sorted(actions, key=lambda item: order.get((item or {}).get("name"), 5))
        while remaining:
            action = remaining.pop(0)
            name = str((action or {}).get("name") or "").strip()
            if name not in ACTION_PROGRESS:
                continue
            args = action.get("args") if isinstance(action.get("args"), dict) else {}
            step, label = ACTION_PROGRESS[name]
            if emit:
                emit(step, f"正在查询{label}", {"action": name})
            tool_started = time.perf_counter()
            try:
                update = self._toolbox.execute_one(name, args, state)
                self._merge_update(state, update)
                state.setdefault("tool_results", {})[name] = update
                record_event("tool", name, "completed", provider="amap_mcp",
                             duration_ms=round((time.perf_counter() - tool_started) * 1000),
                             input_summary={"args": args}, output_summary=summarize_tool_result(update))
                if emit:
                    emit(step, f"已获得{label}", {"action": name, "ok": True})
            except Exception as exc:
                logger.warning("Agent action failed name=%s error=%s", name, exc)
                state.setdefault("tool_results", {})[name] = {"error": str(exc)}
                record_event("tool", name, "failed", provider="amap_mcp",
                             duration_ms=round((time.perf_counter() - tool_started) * 1000),
                             input_summary={"args": args}, error_code=type(exc).__name__)
                if emit:
                    emit(step, f"{label}暂时不可用，继续使用已有信息", {"action": name, "ok": False})
            state.setdefault("executed_actions", []).append(name)
            state["next_actions"] = list(remaining)
            if save:
                save(str(state.get("_phase") or "searching"))
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


# A second execute pass is only used when candidate coverage is insufficient.
plan_execute_replan_agent = PlanExecuteReplanAgent(max_iterations=2)
