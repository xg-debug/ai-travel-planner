from typing import Any, Dict

from app.agents.shared import normalize_preferences


def build_planner_prompt(state: Dict[str, Any]) -> str:
    city = state["city"]
    preferences = normalize_preferences(state.get("preferences", []) or [])
    budget = state.get("budget", "中等")
    travelers = state.get("travelers", 1)
    return f"""
你是旅行规划系统中的 Planner agent。请把用户需求拆成结构化的查询与执行规划。
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
  "attraction_queries": ["用于搜索地标、博物馆、街区和城市体验的查询词，3到6个"],
  "food_queries": ["用于搜索早餐、午晚餐和夜间美食的查询词，3到6个"],
  "hotel_queries": ["用于搜索酒店的查询词，2到4个"],
  "must_have": ["这次行程必须覆盖的体验类型"]
}}

额外要求：
1. attraction_queries 优先围绕真正有代表性的地标、历史街区、博物馆、城市名片，不要泛泛给“城市公园”。
2. food_queries 要优先本地特色早餐、老字号、小吃街区、代表性正餐，不要写“酒店周边早餐”。
3. hotel_queries 要偏向交通便利、口碑较好、适合游客入住的酒店，不需要带“免费”之类价格描述。
4. must_have 要兼顾景点、餐饮、休闲和夜间体验。
"""
