from __future__ import annotations

from typing import Any, Dict, List


TASK_STEP_MESSAGES = {
    "planner_agent": "理解旅行需求并拆分执行任务",
    "attraction_agent": "搜索评分较高的真实景点",
    "food_agent": "搜索本地特色餐饮候选",
    "hotel_agent": "推荐适合路线的酒店",
    "scoring": "根据偏好、天气、预算和路线为候选排序",
    "transport_agent": "评估地点之间的动线与通勤",
    "synthesizer_agent": "整合多类候选并生成行程",
    "poi_agent": "补全景点坐标、图片与故事",
    "reviewer_agent": "审查行程完整性与冲突",
    "workflow_error": "任务调度出现阻塞",
}


def task_router_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return {}


def _task_is_ready(task: Dict[str, Any], completed_tasks: List[str]) -> bool:
    return all(dep in completed_tasks for dep in task.get("depends_on", []))


def get_ready_tasks(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    completed_tasks = list(state.get("completed_tasks", []) or [])
    ready: List[Dict[str, Any]] = []
    for task in state.get("tasks", []) or []:
        if task.get("status") != "pending":
            continue
        if _task_is_ready(task, completed_tasks):
            ready.append(task)
    return ready

def get_ready_task_for_step(state: Dict[str, Any], step: str) -> Dict[str, Any] | None:
    completed_tasks = list(state.get("completed_tasks", []) or [])
    for task in state.get("tasks", []) or []:
        if task.get("step") != step:
            continue
        if task.get("status") != "pending":
            return None
        if _task_is_ready(task, completed_tasks):
            return task
        return None
    return None


def get_task_by_step(state: Dict[str, Any], step: str) -> Dict[str, Any] | None:
    for task in state.get("tasks", []) or []:
        if task.get("step") == step:
            return task
    return None


def task_can_retry(state: Dict[str, Any], step: str) -> bool:
    task = get_task_by_step(state, step)
    if not task:
        return False
    return int(task.get("attempt_count", 0) or 0) < int(task.get("max_attempts", 1) or 1)


def route_next_step(state: Dict[str, Any]) -> str:
    ready_tasks = get_ready_tasks(state)
    if len(ready_tasks) > 1:
        return "parallel_tasks"
    if len(ready_tasks) == 1:
        return str(ready_tasks[0].get("step", ""))
    pending_tasks = [task for task in (state.get("tasks", []) or []) if task.get("status") == "pending"]
    if pending_tasks:
        return "workflow_error"
    return "budget"


def complete_task(state: Dict[str, Any], step: str, result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    result = result or {}
    ready_task = get_ready_task_for_step(state, step)
    tasks = [dict(task) for task in (state.get("tasks", []) or [])]
    task_results = dict(state.get("task_results", {}) or {})
    completed_tasks = list(state.get("completed_tasks", []) or [])

    if not ready_task:
        return {
            "tasks": tasks,
            "task_results": task_results,
            "completed_tasks": completed_tasks,
            "current_task": state.get("current_task"),
        }

    completed_task: Dict[str, Any] | None = None
    ready_task_id = ready_task.get("task_id")
    for task in tasks:
        if task.get("task_id") != ready_task_id:
            continue
        task["status"] = "done"
        task["result"] = result
        task["attempt_count"] = int(task.get("attempt_count", 0) or 0) + 1
        task["error"] = ""
        completed_task = task
        break

    if ready_task_id and ready_task_id not in completed_tasks:
        completed_tasks.append(ready_task_id)
        task_results[ready_task_id] = {
            "step": step,
            "status": "done",
            **result,
        }

    return {
        "tasks": tasks,
        "task_results": task_results,
        "completed_tasks": completed_tasks,
        "current_task": completed_task or ready_task,
    }


def reset_task_chain(
    state: Dict[str, Any],
    steps: List[str],
    reason: str = "",
) -> Dict[str, Any]:
    tasks = [dict(task) for task in (state.get("tasks", []) or [])]
    task_results = dict(state.get("task_results", {}) or {})
    completed_tasks = list(state.get("completed_tasks", []) or [])

    reset_ids: List[str] = []
    for task in tasks:
        if task.get("step") not in steps:
            continue
        task["status"] = "pending"
        task["result"] = {}
        task["error"] = reason
        task_id = str(task.get("task_id", ""))
        if task_id:
            reset_ids.append(task_id)

    for task_id in reset_ids:
        task_results.pop(task_id, None)
        if task_id in completed_tasks:
            completed_tasks.remove(task_id)

    return {
        "tasks": tasks,
        "task_results": task_results,
        "completed_tasks": completed_tasks,
        "current_task": None,
    }
