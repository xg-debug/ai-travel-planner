import logging
from typing import Any, Dict

from app.agents.shared import (
    build_fallback_itinerary,
    extract_itinerary_data,
    extract_json_block,
    normalize_itinerary,
)
from app.core.config import settings
from app.core.llm import invoke_llm_with_fallback

logger = logging.getLogger(__name__)


def planning_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """行程规划 agent：基于查询理解、景点候选与酒店候选生成 itinerary。"""
    logger.info("Planning agent for %s (%s days)", state["city"], state["days"])

    city = state["city"]
    preferences_text = ", ".join(state.get("preferences", [])) if state.get("preferences") else "无特殊偏好"
    budget_level = state.get("budget", "中等")
    travelers = state.get("travelers", 1)
    query_plan = state.get("query_plan", {})
    attraction_candidates = state.get("attraction_candidates", [])[:10]
    hotel_options = state.get("hotel_options", [])[:3]
    attraction_text = "、".join([item.get("name", "") for item in attraction_candidates if item.get("name")]) or "请自行规划真实地点"
    hotel_text = "、".join([item.get("name", "") for item in hotel_options if item.get("name")]) or "可不指定酒店"

    prompt = f"""
    你是旅行规划 agent。请为{travelers}位旅行者生成{city} {state['days']}天行程。
    预算：{budget_level}
    偏好：{preferences_text}
    需求：{state['query']}
    规划重点：{query_plan.get('planning_focus', '')}
    推荐优先使用的真实景点/餐饮/休闲地点：{attraction_text}
    可优先考虑的酒店：{hotel_text}

    要求：
    1. 每天 5-6 个活动，时间从早到晚。
    2. 使用真实地点名称，不要生成“早餐店1-1”这种占位词。
    3. 不同天主题要有差异，减少来回折返。
    4. 每天必须有景点、餐饮、休闲。
    5. 每天都要给出一个推荐酒店，并尽量从可优先考虑的酒店里选择。
    6. 景点/博物馆/乐园/公园等游览类活动要尽量给出明确门票信息；免费项目请写 0。
    7. 早餐请优先安排本地特色早餐、老字号或城市代表性小吃，不要写“酒店周边早餐”这类泛化表达。
    8. 景点请优先选择这座城市更有代表性的特色地标、人文历史、博物馆、经典街区和城市名片，不要整天都安排成公园。

    只返回 JSON 数组，格式：
    [
      {{
        "day": 1,
        "date": "YYYY-MM-DD",
        "theme": "当日主题",
        "summary": "一句话概览",
        "hotel_recommendation": {{
          "name": "酒店名称",
          "price_estimate": 480,
          "address": "酒店地址",
          "reason": "为什么适合这一天"
        }},
        "activities": [
          {{
            "time": "09:00-11:00",
            "title": "活动标题",
            "description": "简要描述",
            "type": "观光游览",
            "location": "真实地点名称",
            "duration": 120,
            "cost_estimate": 80,
            "ticket_price": 60,
            "tips": "实用建议",
            "transportation": "交通方式"
          }}
        ]
      }}
    ]
    """

    try:
        response = invoke_llm_with_fallback(
            prompt,
            temperature=0.6,
            max_tokens=1600,
            request_timeout=24,
            max_retries=0,
            provider_order=[state.get("provider", settings.DEFAULT_LLM_PROVIDER), "deepseek", "openai", "anthropic", "google"],
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        plan_data = extract_json_block(content)
        itinerary = extract_itinerary_data(plan_data)
        if not itinerary:
            raise ValueError("planning agent 返回 itinerary 无效")
        itinerary = normalize_itinerary(itinerary, state)
        return {"plan": itinerary}
    except Exception as exc:
        logger.warning("Planning agent failed, using fallback: %s", exc)
        fallback = normalize_itinerary(build_fallback_itinerary(state), state)
        return {"plan": fallback}
