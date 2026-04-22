import logging
from typing import Any, Dict, List

from app.agents.schemas import PlannerOutput
from app.agents.planner.planner_prompt import build_planner_prompt
from app.agents.shared import build_query_agent_fallback, dedupe, extract_json_block, normalize_preferences
from app.core.config import settings
from app.core.llm import invoke_llm_with_fallback
from app.orchestration.task_models import (
    ATTRACTION_STEP,
    FOOD_STEP,
    HOTEL_STEP,
    POI_STEP,
    REVIEWER_STEP,
    SYNTHESIZER_STEP,
    TRANSPORT_STEP,
    build_task,
)

logger = logging.getLogger(__name__)


def _build_food_queries(state: Dict[str, Any]) -> List[str]:
    city = state["city"]
    preferences = normalize_preferences(state.get("preferences", []) or [])
    food_queries = [
        f"{city}本地特色早餐",
        f"{city}老字号早餐",
        f"{city}高评分特色餐厅",
        f"{city}美食街区",
    ]
    if "food" in preferences:
        food_queries.extend([f"{city}必吃榜餐厅", f"{city}本地人推荐餐厅"])
    if "shopping" in preferences:
        food_queries.append(f"{city}夜市步行街")
    return dedupe(food_queries)


def _build_query_plan(state: Dict[str, Any], parsed: Dict[str, Any] | None) -> Dict[str, Any]:
    query_plan = build_query_agent_fallback(state)
    query_plan["food_queries"] = _build_food_queries(state)
    if not parsed:
        return query_plan
    query_plan.update(
        {
            "travel_style": parsed.get("travel_style") or query_plan["travel_style"],
            "planning_focus": parsed.get("planning_focus") or query_plan["planning_focus"],
            "attraction_queries": dedupe(parsed.get("attraction_queries") or query_plan["attraction_queries"]),
            "food_queries": dedupe(parsed.get("food_queries") or query_plan["food_queries"]),
            "hotel_queries": dedupe(parsed.get("hotel_queries") or query_plan["hotel_queries"]),
            "must_have": parsed.get("must_have") or query_plan["must_have"],
        }
    )
    return query_plan


def _build_execution_plan(state: Dict[str, Any], query_plan: Dict[str, Any]) -> Dict[str, Any]:
    attraction_task = build_task(
        "task_attraction_search",
        ATTRACTION_STEP,
        "attraction_agent",
        "搜索真实景点候选",
        "找出代表性的真实景点、街区与体验地点。",
        inputs={"queries": list(query_plan.get("attraction_queries", []) or []), "must_have": list(query_plan.get("must_have", []) or [])},
    )
    food_task = build_task(
        "task_food_search",
        FOOD_STEP,
        "food_agent",
        "搜索餐饮候选",
        "找出适合早餐、正餐和夜间体验的本地餐饮候选。",
        inputs={"queries": list(query_plan.get("food_queries", []) or []), "must_have": ["早餐", "正餐", "夜生活"]},
    )
    hotel_task = build_task(
        "task_hotel_search",
        HOTEL_STEP,
        "hotel_agent",
        "搜索酒店候选",
        "筛选出适合预算与路线衔接的酒店候选。",
        inputs={"queries": list(query_plan.get("hotel_queries", []) or []), "budget": state.get("budget", "中等")},
    )
    transport_task = build_task(
        "task_transport_plan",
        TRANSPORT_STEP,
        "transport_agent",
        "评估动线与通勤",
        "结合候选地点评估路线顺畅度和推荐交通方式。",
        inputs={"mode": "driving"},
        depends_on=[attraction_task["task_id"], food_task["task_id"], hotel_task["task_id"]],
    )
    synthesizer_task = build_task(
        "task_synthesize_itinerary",
        SYNTHESIZER_STEP,
        "synthesizer_agent",
        "整合生成行程",
        "整合景点、餐饮、住宿和动线结果，生成 itinerary。",
        inputs={"planning_focus": query_plan.get("planning_focus", ""), "travel_style": query_plan.get("travel_style", ""), "must_have": list(query_plan.get("must_have", []) or [])},
        depends_on=[attraction_task["task_id"], food_task["task_id"], hotel_task["task_id"], transport_task["task_id"]],
        max_attempts=2,
    )
    poi_task = build_task(
        "task_poi_enrichment",
        POI_STEP,
        "poi_enrichment_agent",
        "补全 POI 细节",
        "为 itinerary 中的地点补充坐标、图片与故事描述。",
        inputs={"enrichment_fields": ["coordinates", "image", "story"]},
        depends_on=[synthesizer_task["task_id"]],
        max_attempts=2,
    )
    reviewer_task = build_task(
        "task_review_itinerary",
        REVIEWER_STEP,
        "reviewer_agent",
        "审查与修补行程",
        "检查完整性、重复、缺失和明显冲突并修正。",
        inputs={"review_focus": ["完整性", "重复检查", "景点餐饮均衡", "酒店衔接"]},
        depends_on=[poi_task["task_id"]],
        max_attempts=2,
    )
    tasks = [attraction_task, food_task, hotel_task, transport_task, synthesizer_task, poi_task, reviewer_task]
    return {
        "planner_version": "phase3",
        "travel_style": query_plan.get("travel_style", ""),
        "planning_focus": query_plan.get("planning_focus", ""),
        "must_have": list(query_plan.get("must_have", []) or []),
        "strategy_summary": f"先并行搜索景点、餐饮和酒店，再评估动线，随后生成行程、补全 POI 并执行最终审查，目的地为 {state['city']}。",
        "tasks": tasks,
    }


def planner_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    parsed: Dict[str, Any] | None = None
    try:
        response = invoke_llm_with_fallback(
            build_planner_prompt(state),
            temperature=0.3,
            max_tokens=700,
            request_timeout=40,
            max_retries=1,
            provider_order=[state.get("provider", settings.DEFAULT_LLM_PROVIDER), "deepseek", "openai", "anthropic", "google"],
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        raw = extract_json_block(content)
        if isinstance(raw, dict):
            parsed = PlannerOutput.model_validate(raw).model_dump()
        else:
            raise ValueError("planner agent 返回结构无效")
    except Exception as exc:
        logger.warning("Planner agent failed, using fallback: %s", exc)

    query_plan = _build_query_plan(state, parsed)
    execution_plan = _build_execution_plan(state, query_plan)
    return {
        "query_plan": query_plan,
        "execution_plan": execution_plan,
        "tasks": execution_plan["tasks"],
        "task_results": {},
        "completed_tasks": [],
        "current_task": None,
        "reflection_context": {},
        "reflection_history": [],
    }
