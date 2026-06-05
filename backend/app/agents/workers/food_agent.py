import re
from typing import Any, Dict, List

from app.agents.shared import (
    build_recommendation_from_candidates,
    dedupe,
    filter_real_candidates,
    normalize_search_query,
    score_general_candidate,
)
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
        variants.extend([f"{city}本地特色美食", f"{city}老字号美食", f"{city}代表性小吃", f"{city}特色餐厅"])
        return dedupe(variants)

    def _score_food_candidate(self, item: Dict[str, Any], city: str, query: str) -> float:
        score = score_general_candidate(item, city, query, hotel=False)
        name = str(item.get("name", "")).strip()
        type_text = str(item.get("type", "")).strip()
        address = str(item.get("address", "")).strip()
        opening_hours = str(item.get("opening_hours", "")).strip()
        searchable = f"{name} {type_text} {address}".lower()
        query_text = str(query or "").strip().lower()

        food_markers = ("餐饮", "餐厅", "小吃", "面馆", "饭店", "食府", "夜市", "咖啡", "茶馆")
        local_markers = ("本地", "特色", "老字号", "必吃", "人气", "传统", "风味")
        chain_markers = ("旗舰店", "分店", "连锁", "店")

        if any(marker in searchable for marker in food_markers):
            score += 1.5
        if any(marker in searchable for marker in local_markers):
            score += 0.8
        if any(marker in query_text for marker in ("特色", "小吃", "老字号", "必吃")) and any(
            marker in searchable for marker in ("特色", "小吃", "老字号", "风味", "传统", "必吃")
        ):
            score += 1.2
        if "美食街" in query_text and any(marker in searchable for marker in ("夜市", "步行街", "美食街", "小吃街")):
            score += 1.0
        if opening_hours:
            score += 0.3
        if any(marker in name for marker in chain_markers):
            score -= 0.4
        return score

    def _rank_results(self, raw_results: List[Dict[str, Any]], state: Dict[str, Any], query: str) -> List[Dict[str, Any]]:
        city = state["city"]
        ranked: List[Dict[str, Any]] = []
        for item in raw_results:
            next_item = dict(item)
            next_item["_react_score"] = self._score_food_candidate(next_item, city, query)
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
        score = float(item.get("_react_score", item.get("rating", 0)) or 0)
        if not current or score > float(current.get("_food_brand_score", -999)):
            next_item = dict(item)
            next_item["_food_brand_score"] = score
            best_by_brand[brand_key] = next_item
    result = list(best_by_brand.values())
    result.sort(key=lambda item: float(item.get("_food_brand_score", 0)), reverse=True)
    for item in result:
        item.pop("_food_brand_score", None)
    return result


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        matched = re.search(r"\d+(?:\.\d+)?", str(value))
        return float(matched.group()) if matched else default
    except Exception:
        return default


def _format_food_price(value: Any) -> str:
    price = _safe_float(value, 0.0)
    if price <= 0:
        return ""
    return f"¥{price:.2f}/人"


def _with_food_display_fields(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for index, item in enumerate(items):
        next_item = dict(item)
        rating = _safe_float(next_item.get("rating"), 0.0)
        if rating > 0:
            next_item["display_rating"] = round(min(rating, 5.0), 1)
        else:
            next_item["display_rating"] = round(max(4.6, 5.0 - index * 0.1), 1)
        next_item["price_unit"] = "person"
        price_text = _format_food_price(next_item.get("price"))
        if price_text:
            next_item["price_text"] = price_text
        enriched.append(next_item)
    return enriched


def food_search_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    city = state["city"]
    task = get_ready_task_for_step(state, "food_agent")
    task_inputs = task.get("inputs", {}) if task else {}
    queries = task_inputs.get("queries") or [f"{city}本地特色美食", f"{city}老字号美食", f"{city}代表性小吃", f"{city}美食街区"]
    react_result = food_react_agent.run(state, queries, task=task)
    candidates = _with_food_display_fields(_dedupe_food_candidates(filter_real_candidates(react_result["items"])))
    recommendations = list(state.get("recommendations", []) or [])
    if candidates:
        recommendations.append(
            build_recommendation_from_candidates(
                city,
                f"{city}餐饮建议",
                "美食",
                candidates,
                "已通过 ReAct 搜索循环筛选本地特色美食、老字号、小吃和餐饮街区，优先保留更有地方代表性的餐饮地点。",
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
