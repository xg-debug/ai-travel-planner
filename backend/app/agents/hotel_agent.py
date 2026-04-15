from typing import Any, Dict

from app.agents.shared import (
    build_query_agent_fallback,
    build_recommendation_from_candidates,
    collect_ranked_candidates,
)


def hotel_search_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """酒店推荐 agent：搜索适合当前预算和路线的酒店。"""
    city = state["city"]
    query_plan = state.get("query_plan", {})
    queries = query_plan.get("hotel_queries") or build_query_agent_fallback(state)["hotel_queries"]
    hotels = collect_ranked_candidates(queries, city, hotel=True, limit=5)

    recommendations = list(state.get("recommendations", []) or [])
    if hotels:
        recommendations.append(
            build_recommendation_from_candidates(
                city,
                f"{city}住宿建议",
                "酒店",
                hotels,
                "已优先挑选评分更高、位置更方便且更适合衔接整体路线的住宿选项。",
            )
        )
    return {
        "hotel_options": hotels,
        "recommendations": recommendations,
    }
