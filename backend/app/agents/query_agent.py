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
