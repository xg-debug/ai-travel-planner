from typing import Any, Dict

from app.agents.shared import (
    build_query_agent_fallback,
    build_recommendation_from_candidates,
    collect_ranked_candidates,
)


def scenic_search_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """景点搜索 agent：搜索评分更高且适合串联的真实 POI。"""
    city = state["city"]
    query_plan = state.get("query_plan", {})
    queries = query_plan.get("attraction_queries") or build_query_agent_fallback(state)["attraction_queries"]
    candidates = collect_ranked_candidates(queries, city, hotel=False, limit=12)

    recommendations = []
    if candidates:
        recommendations.append(
            build_recommendation_from_candidates(
                city,
                f"{city}高分景点与体验",
                "景点",
                candidates,
                "已基于真实 POI 搜索结果优先筛出评分更高、适合行程串联的景点与餐饮地点。",
            )
        )
    return {
        "attraction_candidates": candidates,
        "recommendations": recommendations,
    }
