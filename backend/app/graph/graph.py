from typing import Dict, Any
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from langgraph.graph import END, StateGraph

from app.agents import (
    attraction_search_agent_node,
    food_search_agent_node,
    hotel_react_agent_node,
    planner_agent_node,
    poi_detail_agent_node,
    reviewer_agent_node,
    synthesizer_agent_node,
    transport_agent_node,
)
from app.graph.nodes import budget_node, risk_notice_node, scoring_node, summary_node, weather_tool_step, workflow_error_node
from app.graph.state import TripState
from app.orchestration.task_router import get_ready_tasks, route_next_step, task_router_node

logger = logging.getLogger(__name__)

NODE_REGISTRY = {
    "planner_agent": planner_agent_node,
    "task_router": task_router_node,
    "parallel_tasks": None,
    "attraction_agent": attraction_search_agent_node,
    "food_agent": food_search_agent_node,
    "hotel_agent": hotel_react_agent_node,
    "scoring": scoring_node,
    "transport_agent": transport_agent_node,
    "synthesizer_agent": synthesizer_agent_node,
    "poi_agent": poi_detail_agent_node,
    "reviewer_agent": reviewer_agent_node,
    "workflow_error": workflow_error_node,
    "weather_tool": weather_tool_step,
    "budget": budget_node,
    "risk_notice": risk_notice_node,
    "summary": summary_node,
}


def parallel_tasks_node(state: Dict[str, Any]) -> Dict[str, Any]:
    ready_tasks = get_ready_tasks(state)
    if len(ready_tasks) <= 1:
        return {}

    step_names = [str(task.get("step", "")) for task in ready_tasks if task.get("step") in NODE_REGISTRY and task.get("step") not in {"parallel_tasks", "task_router"}]
    if not step_names:
        return {}

    results: list[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(len(step_names), 4)) as executor:
        future_map = {
            executor.submit(NODE_REGISTRY[step], dict(state)): step
            for step in step_names
        }
        for future in as_completed(future_map):
            step = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                raise RuntimeError(f"并行执行任务失败 step={step}: {exc}") from exc

    merged: Dict[str, Any] = {
        "tasks": [dict(task) for task in (state.get("tasks", []) or [])],
        "task_results": dict(state.get("task_results", {}) or {}),
        "completed_tasks": list(state.get("completed_tasks", []) or []),
        "current_task": None,
        "recommendations": list(state.get("recommendations", []) or []),
    }

    task_by_id = {str(task.get("task_id", "")): task for task in merged["tasks"]}

    for result in results:
        completed_task = result.get("current_task")
        if isinstance(completed_task, dict):
            task_id = str(completed_task.get("task_id", ""))
            if task_id and task_id in task_by_id:
                task_by_id[task_id] = completed_task
            if task_id and task_id not in merged["completed_tasks"]:
                merged["completed_tasks"].append(task_id)

        for task_id, task_result in (result.get("task_results", {}) or {}).items():
            merged["task_results"][task_id] = task_result

        for key, value in result.items():
            if key in {"tasks", "task_results", "completed_tasks", "current_task"}:
                continue
            if key == "recommendations":
                existing = list(merged.get("recommendations", []) or [])
                seen_titles = {str(item.get("title", "")) for item in existing if isinstance(item, dict)}
                for item in value or []:
                    title = str(item.get("title", "")) if isinstance(item, dict) else ""
                    if title and title in seen_titles:
                        continue
                    if title:
                        seen_titles.add(title)
                    existing.append(item)
                merged["recommendations"] = existing
                continue
            merged[key] = value

    merged["tasks"] = list(task_by_id.values())
    return merged


NODE_REGISTRY["parallel_tasks"] = parallel_tasks_node


def build_trip_graph():
    workflow = StateGraph(TripState)
    for name, node in NODE_REGISTRY.items():
        workflow.add_node(name, node)

    workflow.set_entry_point("planner_agent")
    workflow.add_edge("planner_agent", "weather_tool")
    workflow.add_edge("weather_tool", "task_router")
    workflow.add_conditional_edges(
        "task_router",
        route_next_step,
        {
            "attraction_agent": "attraction_agent",
            "food_agent": "food_agent",
            "hotel_agent": "hotel_agent",
            "scoring": "scoring",
            "parallel_tasks": "parallel_tasks",
            "transport_agent": "transport_agent",
            "synthesizer_agent": "synthesizer_agent",
            "poi_agent": "poi_agent",
            "reviewer_agent": "reviewer_agent",
            "workflow_error": "workflow_error",
            "budget": "budget",
        },
    )
    workflow.add_edge("attraction_agent", "task_router")
    workflow.add_edge("food_agent", "task_router")
    workflow.add_edge("hotel_agent", "task_router")
    workflow.add_edge("scoring", "task_router")
    workflow.add_edge("parallel_tasks", "task_router")
    workflow.add_edge("transport_agent", "task_router")
    workflow.add_edge("synthesizer_agent", "task_router")
    workflow.add_edge("poi_agent", "task_router")
    workflow.add_edge("reviewer_agent", "task_router")
    workflow.add_edge("workflow_error", END)
    workflow.add_edge("budget", "risk_notice")
    workflow.add_edge("risk_notice", "summary")
    workflow.add_edge("summary", END)

    return workflow.compile()


class TripPlanner:
    """旅行规划器。"""

    def __init__(self):
        self.nodes = dict(NODE_REGISTRY)
        self.graph = build_trip_graph()

    def plan_trip(self, state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Starting trip planning process")
        return self.graph.invoke(state)


trip_planner = TripPlanner()
app_trip_graph = trip_planner.graph
