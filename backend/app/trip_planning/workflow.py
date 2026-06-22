from __future__ import annotations

import logging
from typing import Any, Dict, Generator

from app.trip_planning.graph_state import TripPlanningGraphState
from app.trip_planning.nodes import (
    executor_node,
    finalizer_node,
    planner_node,
    replanner_node,
    route_after_replanner,
)
from app.trip_planning.state import TripPlanningState

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - handled at runtime with a clear message.
    END = START = StateGraph = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class TripPlanningWorkflow:
    """LangGraph Plan-Execute-Replan workflow for trip planning."""

    def __init__(self) -> None:
        self._graph = None

    def run(self, initial_state: TripPlanningState) -> TripPlanningState:
        final_state: TripPlanningState = {}
        for event in self.stream(initial_state):
            if event["event"] == "result":
                final_state = dict(event["data"].get("state", {}) or {})
        if not final_state:
            raise RuntimeError("行程规划未生成最终结果")
        return final_state

    def stream(self, initial_state: TripPlanningState) -> Generator[Dict[str, Any], None, None]:
        state = self._initial_graph_state(initial_state)
        logger.info("TripPlanningWorkflow graph started city=%s days=%s", state.get("city"), state.get("days"))
        graph = self._compiled_graph()

        yield self._status("request_analysis", "Planner 正在拆解需求并生成工具计划")
        final_state: Dict[str, Any] = dict(state)
        for chunk in graph.stream(state, config={"recursion_limit": 8}, stream_mode="updates"):
            if not isinstance(chunk, dict):
                continue
            for node_name, update in chunk.items():
                if isinstance(update, dict):
                    final_state.update(update)
                yield from self._events_for_node(str(node_name), final_state)
        yield self._status("budget_estimation", "已完成预算估算")
        yield self._status("risk_notices", "已生成风险提醒")
        yield self._status("summary", "整理最终输出")
        yield {"event": "partial_result", "data": {"state": dict(final_state)}}
        yield {"event": "result", "data": {"state": dict(final_state)}}
        logger.info("TripPlanningWorkflow graph completed city=%s", final_state.get("city"))

    def _compiled_graph(self):
        if self._graph is not None:
            return self._graph
        if StateGraph is None:
            raise RuntimeError("缺少 langgraph 依赖，请在 backend 环境安装 requirements.txt 后重试")

        graph = StateGraph(TripPlanningGraphState)
        graph.add_node("planner", planner_node)
        graph.add_node("executor", executor_node)
        graph.add_node("replanner", replanner_node)
        graph.add_node("finalizer", finalizer_node)
        graph.add_edge(START, "planner")
        graph.add_edge("planner", "executor")
        graph.add_edge("executor", "replanner")
        graph.add_conditional_edges(
            "replanner",
            route_after_replanner,
            {"executor": "executor", "planner": "planner", "finalizer": "finalizer"},
        )
        graph.add_edge("finalizer", END)
        self._graph = graph.compile()
        return self._graph

    def _initial_graph_state(self, state: TripPlanningState) -> TripPlanningGraphState:
        return {
            **dict(state),
            "planning_brief": {},
            "action_plan": {},
            "next_actions": [],
            "executed_actions": [],
            "tool_results": {},
            "replan_request": "",
            "replanner_decision": "continue",
            "replanner_reason": "",
            "iteration": 0,
            "max_iterations": 2,
            "recommendations": [],
        }

    def _status(self, step: str, message: str, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"step": step, "message": message}
        if extra:
            payload.update(extra)
        return {"event": "status", "data": payload}

    def _events_for_node(self, node_name: str, state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        if node_name == "planner":
            yield self._status("weather_lookup", "Executor 正在查询天气、景点、美食、住宿和交通")
            return
        if node_name == "executor":
            yield self._status(
                "attraction_search",
                "已完成景点候选查询",
                {"count": len(state.get("attraction_candidates", []) or [])},
            )
            yield self._status(
                "food_search",
                "已完成美食候选查询",
                {"count": len(state.get("food_candidates", []) or [])},
            )
            yield self._status(
                "hotel_search",
                "已完成住宿候选生成",
                {"count": len(state.get("hotel_options", []) or [])},
            )
            yield self._status("transport_planning", "已完成往返交通评估")
            yield self._status(
                "itinerary_review",
                "Replanner 正在检查工具结果并决定是否补充执行",
                {
                    "attractions": len(state.get("attraction_candidates", []) or []),
                    "foods": len(state.get("food_candidates", []) or []),
                    "hotels": len(state.get("hotel_options", []) or []),
                },
            )
            return
        if node_name == "replanner":
            decision = state.get("replanner_decision") or "final"
            if decision == "continue":
                yield self._status("weather_lookup", "Replanner 要求补充查询，Executor 正在继续执行")
            elif decision == "replan":
                yield self._status("request_analysis", "Replanner 要求重规划，Planner 正在调整策略")
            else:
                yield self._status("itinerary_synthesis", "Finalizer 正在生成最终每日行程")
            return
        if node_name == "finalizer":
            yield {"event": "partial_result", "data": {"state": dict(state)}}


trip_planning_workflow = TripPlanningWorkflow()
