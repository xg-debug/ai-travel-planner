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
from app.tools.amap_tools import search_hotels_tool


class HotelReActAgent(BaseReActAgent):
    name = "hotel_agent"
    tool_name = "search_hotels"
    result_limit = 5
    min_target_results = 4

    def expand_query(self, query: str, city: str) -> List[str]:
        return normalize_search_query(query, city) or [query]

    def _rank_results(self, raw_results: List[Dict[str, Any]], state: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        city = state["city"]
        ranked: List[Dict[str, Any]] = []
        for item in raw_results:
            next_item = dict(item)
            next_item["_react_score"] = score_general_candidate(next_item, city, query, hotel=True)
            ranked.append(next_item)
        ranked.sort(key=lambda item: float(item.get("_react_score", 0)), reverse=True)
        return ranked


hotel_react_agent = HotelReActAgent(lambda query, city, size: search_hotels_tool(query, city, size))


def hotel_react_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    city = state["city"]
    query_plan = state.get("query_plan", {})
    task = get_ready_task_for_step(state, "hotel_agent")
    task_inputs = task.get("inputs", {}) if task else {}
    queries = task_inputs.get("queries") or query_plan.get("hotel_queries") or build_query_agent_fallback(state)["hotel_queries"]
    react_result = hotel_react_agent.run(state, queries, task=task)
    hotels = filter_real_candidates(react_result["items"], allow_sources={"hotel", "agentichotel", "geo", "amap"})
    recommendations = list(state.get("recommendations", []) or [])
    if hotels:
        recommendations.append(
            build_recommendation_from_candidates(
                city,
                f"{city}住宿建议",
                "酒店",
                hotels,
                "已通过 ReAct 搜索循环多轮筛选住宿，优先保留评分更高、位置更方便的酒店候选。",
            )
        )
    return {
        "hotel_options": hotels,
        "recommendations": recommendations,
        **complete_task(
            state,
            "hotel_agent",
            build_task_result(
                output={"items": hotels[:5]},
                metrics={"hotel_count": len(hotels), "recommendation_count": len(recommendations)},
                trace=react_result["react_trace"],
                quality={"match": "high" if len(hotels) >= 3 else "medium"},
                summary=f"已完成酒店搜索，收集 {len(hotels)} 个住宿候选。",
                used_fallback=False,
            ) | {"react_summary": react_result["react_summary"]},
        ),
    }
