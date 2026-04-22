from typing import Any, Dict

from app.orchestration.task_router import route_next_step


def run_planned_tasks(nodes: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    iterations = 0
    while True:
        next_step = route_next_step(state)
        if next_step in {"weather_tool", "workflow_error"}:
            if next_step == "workflow_error":
                state.update(nodes[next_step](state))
            return state
        iterations += 1
        if iterations > 64:
            raise RuntimeError("任务工作流执行次数超过上限，疑似进入循环。")
        state.update(nodes[next_step](state))
