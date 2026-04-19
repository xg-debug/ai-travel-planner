import logging
from typing import Any, Dict

from app.agents.shared import build_query_agent_fallback, dedupe, extract_json_block
from app.core.config import settings
from app.core.llm import invoke_llm_with_fallback

logger = logging.getLogger(__name__)


def query_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """规划查询 agent：把自然语言需求变成搜索与规划意图。"""
    city = state["city"]
    preferences = state.get("preferences", []) or []
    budget = state.get("budget", "中等")
    travelers = state.get("travelers", 1)

    prompt = f"""
    你是旅行查询理解 agent。请把用户的旅游需求拆成结构化 JSON。
    城市：{city}
    天数：{state['days']}
    人数：{travelers}
    预算：{budget}
    偏好：{', '.join(preferences) if preferences else '无特殊偏好'}
    需求：{state['query']}

    返回 JSON 对象：
    {{
      "travel_style": "一句话总结出行风格",
      "planning_focus": "一句话说明路线规划重点",
      "attraction_queries": ["用于搜索真实景点/餐厅/休闲地点的查询词，3到6个"],
      "hotel_queries": ["用于搜索酒店的查询词，2到4个"],
      "must_have": ["这次行程必须覆盖的体验类型"]
    }}

    额外要求：
    1. attraction_queries 优先围绕这座城市真正有代表性的地标、历史街区、博物馆、城市名片、美食街区，不要泛泛给“城市公园”这类兜底词，除非用户明确偏好自然/公园。
    2. 早餐相关查询要优先本地特色早餐、老字号早餐、小吃店，不要写“酒店周边早餐”。
    3. hotel_queries 要偏向交通便利、口碑较好、适合游客入住的酒店，不需要带“免费”之类价格描述。
    """

    try:
        response = invoke_llm_with_fallback(
            prompt,
            temperature=0.3,
            max_tokens=500,
            request_timeout=18,
            max_retries=0,
            provider_order=[state.get("provider", settings.DEFAULT_LLM_PROVIDER), "deepseek", "openai", "anthropic", "google"],
        )
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = extract_json_block(content)
        if not isinstance(parsed, dict):
            raise ValueError("query agent 返回结构无效")
        fallback = build_query_agent_fallback(state)
        fallback.update(
            {
                "travel_style": parsed.get("travel_style") or fallback["travel_style"],
                "planning_focus": parsed.get("planning_focus") or fallback["planning_focus"],
                "attraction_queries": dedupe(parsed.get("attraction_queries") or fallback["attraction_queries"]),
                "hotel_queries": dedupe(parsed.get("hotel_queries") or fallback["hotel_queries"]),
                "must_have": parsed.get("must_have") or fallback["must_have"],
            }
        )
        return {"query_plan": fallback}
    except Exception as exc:
        logger.warning("Query agent failed, using fallback: %s", exc)
        return {"query_plan": build_query_agent_fallback(state)}
