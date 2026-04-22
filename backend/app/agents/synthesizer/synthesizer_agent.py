import logging
from typing import Any, Dict

from app.agents.schemas import ItineraryDayModel
from app.agents.shared import build_fallback_itinerary, extract_itinerary_data, extract_json_block, normalize_itinerary
from app.core.config import settings
from app.core.llm import invoke_llm_with_fallback
from app.orchestration.task_models import build_task_result
from app.orchestration.task_router import complete_task, get_ready_task_for_step

logger = logging.getLogger(__name__)


def synthesizer_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Synthesizing itinerary for %s (%s days)", state["city"], state["days"])
    city = state["city"]
    preferences_text = ", ".join(state.get("preferences", [])) if state.get("preferences") else "无特殊偏好"
    budget_level = state.get("budget", "中等")
    travelers = state.get("travelers", 1)
    query_plan = state.get("query_plan", {})
    task = get_ready_task_for_step(state, "synthesizer_agent")
    task_inputs = task.get("inputs", {}) if task else {}
    attraction_candidates = state.get("attraction_candidates", [])[:8]
    food_candidates = state.get("food_candidates", [])[:6]
    hotel_options = state.get("hotel_options", [])[:3]
    transport_plan = state.get("transport_plan", {}) or {}
    reflection_context = state.get("reflection_context", {}) or {}
    attraction_text = "、".join([item.get("name", "") for item in attraction_candidates if item.get("name")]) or "请自行规划真实地点"
    food_text = "、".join([item.get("name", "") for item in food_candidates if item.get("name")]) or "请优先安排本地特色餐饮"
    hotel_text = "、".join([item.get("name", "") for item in hotel_options if item.get("name")]) or "可不指定酒店"
    rerun_hint = ""
    if reflection_context.get("action") == "rerun_synthesizer":
        rerun_hint = f"""
你正在根据上一轮 reflection 结果重写 itinerary。
上一轮问题摘要：{reflection_context.get('summary', '')}
必须优先修复的问题：{reflection_context.get('issues', [])[:6]}
请不要重复上一轮中被标记的问题地点或节奏安排。
"""

    prompt = f"""
你是旅行行程 synthesizer agent。请为{travelers}位旅行者生成{city} {state['days']}天行程。
预算：{budget_level}
偏好：{preferences_text}
需求：{state['query']}
规划重点：{task_inputs.get('planning_focus') or query_plan.get('planning_focus', '')}
景点候选：{attraction_text}
餐饮候选：{food_text}
酒店候选：{hotel_text}
动线摘要：{transport_plan.get('summary', '')}
{rerun_hint}

要求：
1. 每天 5-6 个活动，时间从早到晚。
2. 每天必须同时覆盖景点、餐饮、休闲。
3. 早餐、午餐或晚餐尽量优先使用餐饮候选中的真实地点。
4. 优先围绕更顺路的地点生成，减少来回折返。
5. 每天都要有一个推荐酒店，并尽量从酒店候选里选择。
6. 使用真实地点，不要使用占位词。

只返回 JSON 数组，格式与既有 itinerary 一致。
"""

    try:
        response = invoke_llm_with_fallback(
            prompt,
            temperature=0.6,
            max_tokens=1800,
            request_timeout=45,
            max_retries=1,
            provider_order=[state.get("provider", settings.DEFAULT_LLM_PROVIDER), "deepseek", "openai", "anthropic", "google"],
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        itinerary = extract_itinerary_data(extract_json_block(content))
        if not itinerary:
            raise ValueError("synthesizer agent 返回 itinerary 无效")
        itinerary = [ItineraryDayModel.model_validate(day).model_dump() for day in itinerary]
        itinerary = normalize_itinerary(itinerary, state)
        return {
            "draft_plan": itinerary,
            "plan": itinerary,
            "reflection_context": {},
            **complete_task(
                state,
                "synthesizer_agent",
                build_task_result(
                    output={"day_count": len(itinerary)},
                    metrics={"day_count": len(itinerary)},
                    quality={"status": "draft_ready"},
                    summary=f"已整合候选结果并生成 {len(itinerary)} 天 itinerary 草案。",
                ),
            ),
        }
    except Exception as exc:
        logger.warning("Synthesizer failed, using fallback: %s", exc)
        fallback = normalize_itinerary(build_fallback_itinerary(state), state)
        return {
            "draft_plan": fallback,
            "plan": fallback,
            "reflection_context": {},
            **complete_task(
                state,
                "synthesizer_agent",
                build_task_result(
                    output={"day_count": len(fallback)},
                    metrics={"day_count": len(fallback)},
                    summary="synthesizer 调用失败，已使用兜底 itinerary。",
                    used_fallback=True,
                ),
            ),
        }
