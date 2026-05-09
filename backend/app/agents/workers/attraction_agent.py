from typing import Any, Dict, List

from app.agents.shared import (
    build_query_agent_fallback,
    build_recommendation_from_candidates,
    filter_real_candidates,
    normalize_search_query,
    score_general_candidate,
)
from app.agents.workers.base_react_agent import BaseReActAgent
from app.orchestration.task_models import build_task_result
from app.orchestration.task_router import complete_task, get_ready_task_for_step
from app.tools.amap_tools import search_pois_tool


class AttractionReActAgent(BaseReActAgent):
    name = "attraction_agent"
    tool_name = "search_pois"
    result_limit = 12
    min_target_results = 8

    def expand_query(self, query: str, city: str) -> List[str]:
        return normalize_search_query(query, city) or [query]

    def _rank_results(self, raw_results: List[Dict[str, Any]], state: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        city = state["city"]
        ranked: List[Dict[str, Any]] = []
        for item in raw_results:
            next_item = dict(item)
            next_item["_react_score"] = score_general_candidate(next_item, city, query, hotel=False)
            ranked.append(next_item)
        ranked.sort(key=lambda item: float(item.get("_react_score", 0)), reverse=True)
        return ranked


attraction_react_agent = AttractionReActAgent(lambda query, city, size: search_pois_tool(query, city, size))


def attraction_search_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    city = state["city"]
    query_plan = state.get("query_plan", {})
    task = get_ready_task_for_step(state, "attraction_agent")
    task_inputs = task.get("inputs", {}) if task else {}
    queries = task_inputs.get("queries") or query_plan.get("attraction_queries") or build_query_agent_fallback(state)["attraction_queries"]
    react_result = attraction_react_agent.run(state, queries, task=task)
    candidates = filter_real_candidates(react_result["items"])
    recommendations = list(state.get("recommendations", []) or [])
    if candidates:
        recommendations.append(
            build_recommendation_from_candidates(
                city,
                f"{city}高分景点与体验",
                "景点",
                candidates,
                "已通过 ReAct 搜索循环多轮筛选真实 POI，优先保留更有代表性且适合行程串联的地点。",
            )
        )
    return {
        "attraction_candidates": candidates,
        "recommendations": recommendations,
        **complete_task(
            state,
            "attraction_agent",
            build_task_result(
                output={"items": candidates[:8]},
                metrics={"candidate_count": len(candidates), "recommendation_count": len(recommendations)},
                trace=react_result["react_trace"],
                quality={"coverage": "high" if len(candidates) >= 8 else "medium"},
                summary=f"已完成景点候选搜索，收集 {len(candidates)} 个候选。",
                used_fallback=False,
            ) | {"react_summary": react_result["react_summary"]},
        ),
    }
