import re
from typing import Any, Dict, List

from app.agents.city_knowledge import has_branch_marker, score_food_locality
from app.agents.shared import build_recommendation_from_candidates, dedupe, normalize_search_query, score_general_candidate
from app.agents.workers.base_react_agent import BaseReActAgent
from app.orchestration.task_models import build_task_result
from app.orchestration.task_router import complete_task, get_ready_task_for_step
from app.tools.amap_tools import search_pois_tool


class FoodReActAgent(BaseReActAgent):
    name = "food_agent"
    tool_name = "search_pois"
    result_limit = 10
    min_target_results = 6

    def expand_query(self, query: str, city: str) -> List[str]:
        variants = normalize_search_query(query, city) or [query]
        variants.extend([f"{city}早餐", f"{city}本地小吃", f"{city}特色餐厅"])
        return dedupe(variants)

    def _rank_results(self, raw_results: List[Dict[str, Any]], state: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        city = state["city"]
        ranked: List[Dict[str, Any]] = []
        for item in raw_results:
            next_item = dict(item)
            searchable = f"{next_item.get('name', '')} {next_item.get('type', '')} {next_item.get('address', '')}"
            bonus = score_food_locality(searchable, city, query)
            next_item["_react_score"] = score_general_candidate(next_item, city, query, hotel=False) + bonus + 2.5
            ranked.append(next_item)
        ranked.sort(key=lambda item: float(item.get("_react_score", 0)), reverse=True)
        return ranked


food_react_agent = FoodReActAgent(lambda query, city, size: search_pois_tool(query, city, size))


def _normalize_food_brand(name: str) -> str:
    text = str(name or "").strip()
    text = re.sub(r"[（(].*?[)）]", "", text)
    text = re.sub(r"(旗舰店|总店|分店|[一二三四五六七八九十\d]+店)$", "", text)
    text = re.sub(r"\s+", "", text)
    return text


def _dedupe_food_candidates(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best_by_brand: Dict[str, Dict[str, Any]] = {}
    for item in items:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        brand_key = _normalize_food_brand(name)
        current = best_by_brand.get(brand_key)
        score = float(item.get("rating", 0) or 0) - (0.6 if has_branch_marker(name) else 0)
        if not current or score > float(current.get("_food_brand_score", -999)):
            next_item = dict(item)
            next_item["_food_brand_score"] = score
            best_by_brand[brand_key] = next_item
    result = list(best_by_brand.values())
    result.sort(key=lambda item: float(item.get("_food_brand_score", 0)), reverse=True)
    for item in result:
        item.pop("_food_brand_score", None)
    return result


def food_search_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    city = state["city"]
    task = get_ready_task_for_step(state, "food_agent")
    task_inputs = task.get("inputs", {}) if task else {}
    queries = task_inputs.get("queries") or [f"{city}本地特色早餐", f"{city}高评分特色餐厅", f"{city}夜市步行街"]
    react_result = food_react_agent.run(state, queries, task=task)
    candidates = _dedupe_food_candidates(react_result["items"])
    recommendations = list(state.get("recommendations", []) or [])
    if candidates:
        recommendations.append(
            build_recommendation_from_candidates(
                city,
                f"{city}餐饮建议",
                "美食",
                candidates,
                "已通过 ReAct 搜索循环筛选早餐、正餐和夜间美食候选，优先保留更有地方特色的餐饮地点。",
            )
        )
    return {
        "food_candidates": candidates,
        "recommendations": recommendations,
        **complete_task(
            state,
            "food_agent",
            build_task_result(
                output={"items": candidates[:8]},
                metrics={"candidate_count": len(candidates), "recommendation_count": len(recommendations)},
                trace=react_result["react_trace"],
                quality={"locality": "high" if len(candidates) >= 4 else "medium"},
                summary=f"已完成餐饮候选搜索，收集 {len(candidates)} 个本地餐饮候选。",
                used_fallback=False,
            ) | {"react_summary": react_result["react_summary"]},
        ),
    }
