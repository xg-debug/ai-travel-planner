from typing import Any, Dict, List


PLANNER_STEP = "planner_agent"
ATTRACTION_STEP = "attraction_agent"
FOOD_STEP = "food_agent"
HOTEL_STEP = "hotel_agent"
SCORING_STEP = "scoring"
TRANSPORT_STEP = "transport_agent"
SYNTHESIZER_STEP = "synthesizer_agent"
POI_STEP = "poi_agent"
REVIEWER_STEP = "reviewer_agent"


def build_task(
    task_id: str,
    step: str,
    agent: str,
    title: str,
    goal: str,
    inputs: Dict[str, Any] | None = None,
    depends_on: List[str] | None = None,
    max_attempts: int = 1,
) -> Dict[str, Any]:
    return {
        "task_id": task_id,
        "step": step,
        "agent": agent,
        "title": title,
        "goal": goal,
        "depends_on": list(depends_on or []),
        "status": "pending",
        "attempt_count": 0,
        "max_attempts": max_attempts,
        "result": {},
        "error": "",
        "inputs": dict(inputs or {}),
    }


def build_task_result(
    *,
    output: Dict[str, Any] | None = None,
    metrics: Dict[str, Any] | None = None,
    trace: List[Dict[str, Any]] | None = None,
    quality: Dict[str, Any] | None = None,
    summary: str = "",
    used_fallback: bool = False,
) -> Dict[str, Any]:
    return {
        "output": dict(output or {}),
        "metrics": dict(metrics or {}),
        "trace": list(trace or []),
        "quality": dict(quality or {}),
        "summary": summary,
        "used_fallback": used_fallback,
    }
