import logging
from typing import Any, Dict, List

from app.agents.workers.task_execution_agent import BaseTaskExecutionAgent
from app.orchestration.task_models import build_task_result
from app.orchestration.task_router import complete_task, get_ready_task_for_step
from app.tools.amap_tools import calculate_route_tool

logger = logging.getLogger(__name__)


def _format_route_input(item: Dict[str, Any]) -> str:
    lat = item.get("lat")
    lng = item.get("lng")
    coordinates = item.get("coordinates") or {}
    if lat is None:
        lat = coordinates.get("lat")
    if lng is None:
        lng = coordinates.get("lng")
    if lat is not None and lng is not None:
        return f"{lng},{lat}"
    return str(item.get("address", "") or item.get("name", "")).strip()


class TransportExecutionAgent(BaseTaskExecutionAgent):
    name = "transport_agent"
    max_steps = 8

    def build_initial_context(self, state: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        task_inputs = task.get("inputs", {}) if task else {}
        mode = str(task_inputs.get("mode", "driving"))
        hotels = state.get("hotel_options", []) or []
        attractions = state.get("attraction_candidates", []) or []
        foods = state.get("food_candidates", []) or []

        chain: List[Dict[str, Any]] = []
        if hotels:
            chain.append(hotels[0])
        if attractions:
            chain.append(attractions[0])
        if foods:
            chain.append(foods[0])
        if len(attractions) > 1:
            chain.append(attractions[1])
        if len(foods) > 1:
            chain.append(foods[1])

        pending_pairs: List[Dict[str, Any]] = []
        for idx in range(len(chain) - 1):
            pending_pairs.append(
                {
                    "origin": chain[idx],
                    "destination": chain[idx + 1],
                    "label": f"{chain[idx].get('name', '')} -> {chain[idx + 1].get('name', '')}",
                }
            )

        return {
            "mode": mode,
            "pending_pairs": pending_pairs,
            "built_legs": [],
            "total_distance": 0,
            "total_duration": 0,
            "summary_ready": False,
        }

    def available_actions(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        actions: List[str] = []
        if context.get("pending_pairs"):
            actions.append("calculate_leg")
        if context.get("built_legs") and not context.get("summary_ready"):
            actions.append("summarize_route")
        actions.append("finish")
        return actions

    def perform_action(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], action: Dict[str, Any], trace_entry: Dict[str, Any]) -> Dict[str, Any]:
        next_context = {**context}
        action_name = action.get("action")
        if action_name == "calculate_leg":
            pending_pairs = list(next_context.get("pending_pairs", []))
            if not pending_pairs:
                trace_entry["observation"] = "没有可计算的路线段。"
                return next_context

            pair = pending_pairs.pop(0)
            origin = pair["origin"]
            destination = pair["destination"]
            try:
                route = calculate_route_tool(_format_route_input(origin), _format_route_input(destination), next_context.get("mode", "driving"))
            except Exception as exc:
                logger.warning("transport route failed: %s", exc)
                route = {"distance": 0, "duration": 0, "steps": [], "fallback": True}

            duration = int(route.get("duration", 0) or 0)
            distance = int(route.get("distance", 0) or 0)
            next_context["pending_pairs"] = pending_pairs
            next_context["total_duration"] = int(next_context.get("total_duration", 0) or 0) + duration
            next_context["total_distance"] = int(next_context.get("total_distance", 0) or 0) + distance
            next_context["built_legs"] = list(next_context.get("built_legs", [])) + [
                {
                    "from": origin.get("name", ""),
                    "to": destination.get("name", ""),
                    "duration_minutes": duration // 60 if duration else 0,
                    "distance_km": round(distance / 1000, 1) if distance else 0,
                    "mode": next_context.get("mode", "driving"),
                    "fallback": bool(route.get("fallback")),
                }
            ]
            trace_entry["target"] = pair.get("label", "")
            trace_entry["observation"] = f"已计算 1 段路线，累计 {len(next_context['built_legs'])} 段。"
            return next_context

        if action_name == "summarize_route":
            legs = list(next_context.get("built_legs", []))
            if legs:
                route_style = "优先围绕同一区域串联景点、餐饮与酒店，减少来回折返。"
                if any(leg.get("fallback") for leg in legs):
                    route_style = "部分路线使用降级估算，建议出行前再次确认导航结果。"
                next_context["summary"] = route_style
            else:
                next_context["summary"] = "缺少足够候选点，无法生成详细动线。"
            next_context["summary_ready"] = True
            trace_entry["observation"] = next_context["summary"]
        return next_context

    def should_finish(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], trace: List[Dict[str, Any]]) -> bool:
        return not context.get("pending_pairs") and bool(context.get("summary_ready"))

    def finalize(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        legs = list(context.get("built_legs", []))
        transport_plan = {
            "mode": context.get("mode", "driving"),
            "legs": legs,
            "total_duration_minutes": int(context.get("total_duration", 0) or 0) // 60 if context.get("total_duration") else 0,
            "total_distance_km": round(int(context.get("total_distance", 0) or 0) / 1000, 1) if context.get("total_distance") else 0,
            "summary": context.get("summary") or ("优先围绕同一区域串联景点、餐饮与酒店，减少来回折返。" if legs else "缺少足够候选点，无法生成详细动线。"),
        }
        return {
            "transport_plan": transport_plan,
            "task_result": build_task_result(
                output={"plan": transport_plan},
                metrics={
                    "legs": len(legs),
                    "distance_km": transport_plan["total_distance_km"],
                    "duration_minutes": transport_plan["total_duration_minutes"],
                },
                trace=trace,
                summary=transport_plan["summary"],
                used_fallback=bool(legs and any(leg.get("fallback") for leg in legs)),
            ),
        }


transport_execution_agent = TransportExecutionAgent()


def transport_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    task = get_ready_task_for_step(state, "transport_agent")
    execution_result = transport_execution_agent.run(state, task=task)
    transport_plan = execution_result["transport_plan"]
    task_result = execution_result["task_result"]
    return {
        "transport_plan": transport_plan,
        **complete_task(state, "transport_agent", task_result),
    }
