from __future__ import annotations

import json
from typing import Any, Dict, List


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def build_planner_prompt(state: Dict[str, Any]) -> str:
    context = {
        "city": state.get("city", ""),
        "departure_city": state.get("departure_city", ""),
        "days": state.get("days", 1),
        "travelers": state.get("travelers", 1),
        "start_date": state.get("start_date", ""),
        "budget_level": state.get("budget", "中等"),
        "budget_amount": state.get("budget_amount", 0),
        "accommodation_preference": state.get("accommodation_preference", "mid-range"),
        "preferences": state.get("preferences", []) or [],
        "query": state.get("query", ""),
        "replan_request": state.get("replan_request", ""),
    }
    return f"""你是旅行规划 Planner。请先理解用户需求，再决定 Executor 需要调用哪些工具。

目标：让后续规划覆盖不同类型景点，不要多天围绕同一个地点；酒店只给住宿档位匹配建议，不要求实时房价。

用户需求：
{to_json(context)}

请只返回 JSON：
{{
  "planning_brief": {{
    "travel_style": "旅行风格",
    "user_priorities": ["优先级"],
    "area_strategy": "区域和动线思路",
    "hotel_strategy": "住宿档位和位置策略",
    "budget_strategy": "预算策略"
  }},
  "actions": [
    {{"name": "get_weather", "args": {{"city": "目的地", "days": 3}}}},
    {{"name": "search_attractions", "args": {{"queries": ["查询词1", "查询词2"]}}}},
    {{"name": "search_foods", "args": {{"queries": ["查询词1", "查询词2"]}}}},
    {{"name": "recommend_hotels", "args": {{"areas": ["建议住宿区域"], "count": 5}}}},
    {{"name": "plan_transport", "args": {{}}}}
  ]
}}

要求：
- search_attractions 查询词要体现用户偏好，并覆盖经典、城市特色、自然/街区/夜间等差异化方向。
- 先搜索景点和酒店，再 search_foods；系统会按景点与酒店坐标搜索周边餐厅。
- search_foods 查询词要避开大学食堂、单位食堂、内部餐厅，优先本地特色、老字号、街区餐厅。
- 不要输出 Markdown，不要解释。"""


def build_replanner_prompt(state: Dict[str, Any]) -> str:
    context = {
        "request": {
            "city": state.get("city", ""),
            "days": state.get("days", 1),
            "preferences": state.get("preferences", []) or [],
            "budget_amount": state.get("budget_amount", 0),
            "accommodation_preference": state.get("accommodation_preference", ""),
        },
        "planning_brief": state.get("planning_brief", {}),
        "iteration": state.get("iteration", 0),
        "max_iterations": state.get("max_iterations", 2),
        "tool_result_summary": _tool_result_summary(state),
    }
    return f"""你是旅行规划 Replanner。请检查 Executor 的结果是否足以生成最终每日行程。

判断重点：
- 景点候选是否足够覆盖 {state.get("days", 1)} 天，且不要全是同一类型。
- 餐饮候选不能以大学食堂、单位食堂、内部餐厅为主要推荐。
- 酒店是否匹配住宿档位和预算预期。
- 信息不足时，只补最关键的下一步工具动作，避免无限查询。

上下文：
{to_json(context)}

只返回 JSON：
{{
  "decision": "continue | replan | final",
  "reason": "一句话说明",
  "next_actions": [
    {{"name": "search_attractions", "args": {{"queries": ["补充查询词"]}}}}
  ],
  "replan_request": "如果需要重新规划，写给 Planner 的要求"
}}
"""


def build_finalizer_prompt(state: Dict[str, Any]) -> str:
    days = int(state.get("days", 1) or 1)
    context = {
        "request": {
            "city": state.get("city", ""),
            "departure_city": state.get("departure_city", ""),
            "days": days,
            "travelers": state.get("travelers", 1),
            "start_date": state.get("start_date", ""),
            "budget_level": state.get("budget", "中等"),
            "budget_amount": state.get("budget_amount", 0),
            "accommodation_preference": state.get("accommodation_preference", "mid-range"),
            "preferences": state.get("preferences", []) or [],
            "query": state.get("query", ""),
        },
        "planning_brief": state.get("planning_brief", {}),
        "weather": _weather_context(state),
        "attractions": _top_items(state.get("attraction_candidates", []) or [], max(12, days * 5)),
        "foods": _top_items(state.get("food_candidates", []) or [], max(10, days * 3)),
        "hotels": _top_items(state.get("hotel_options", []) or [], 6),
        "intercity_transport": state.get("intercity_transport", {}),
        "replanner_reason": state.get("replanner_reason", ""),
    }
    return f"""你是旅行规划 Finalizer。请基于工具结果生成最终每日行程。

硬性要求：
- 输出 {days} 天，每天必须有不同的主要景点/体验，不要三天都围绕同一个地点。
- 优先使用候选 attractions/foods/hotels 中的真实名称；location 不要重复写地址。
- 每天 2-4 个景点/体验 + 午餐/晚餐；不要安排下午茶。
- 餐饮不要推荐大学食堂、单位食堂、内部食堂。
- 酒店推荐使用同一套 hotel_options，确保总览和每日行程一致。
- 酒店价格只能写“参考区间/估算”，不要装作实时房价。
- candidates 中如有 opening_hours，请写入活动 tips；如有 avg_cost/price，请作为参考消费使用。
- cost_estimate 表示本活动按全部 travelers 估算的总费用；餐饮可按 avg_cost * travelers 估算。
- ticket_price 表示单人门票参考价；无法确认时填 0，不要编造精确票价。
- 不要把高德地点参考消费当作酒店实时房价或景区实时票价。
- accommodation_preference 为 budget/mid-range/luxury 时，分别对应经济/中档/高档住宿，并在 reason 中说明匹配理由。
- 若 budget_amount > 0，总预算尽量贴近预算但不强行编低价格。
- 所有文字用简体中文，只返回合法 JSON。

上下文：
{to_json(context)}

返回结构：
{{
  "itinerary": [
    {{
      "day": 1,
      "date": "YYYY-MM-DD 或 null",
      "theme": "当天主题",
      "summary": "当天安排概览",
      "weather_advice": "天气建议",
      "hotel_recommendation": {{
        "name": "酒店名",
        "price_estimate": "参考价格区间",
        "price_is_estimated": true,
        "address": "区域或地址",
        "reason": "为什么匹配用户选择的住宿档位",
        "source": "llm_hotel",
        "source_id": "hotel id",
        "coordinates": {{"lat": 0, "lng": 0}}
      }},
      "activities": [
        {{
          "time": "09:30-11:30",
          "title": "活动标题",
          "description": "简短说明",
          "type": "景点游览/美食餐饮/休闲体验/交通衔接",
          "location": "地点名",
          "duration": 90,
          "cost_estimate": 0,
          "ticket_price": 0,
          "tips": "提示",
          "opening_hours": "营业/开放时间，未知则空字符串",
          "price_note": "价格来源提醒，未知则空字符串",
          "transportation": "到下一站的交通建议",
          "source": "geo/amap/tencet/llm",
          "source_id": "候选 id",
          "coordinates": {{"lat": 0, "lng": 0}}
        }}
      ]
    }}
  ],
  "final_output": "Markdown 行程总结"
}}"""


def build_hotel_prompt(state: Dict[str, Any], areas: List[str], count: int) -> str:
    context = {
        "city": state.get("city", ""),
        "days": state.get("days", 1),
        "travelers": state.get("travelers", 1),
        "budget_amount": state.get("budget_amount", 0),
        "budget_level": state.get("budget", "中等"),
        "accommodation_preference": state.get("accommodation_preference", "mid-range"),
        "preferences": state.get("preferences", []) or [],
        "areas": areas,
        "planning_brief": state.get("planning_brief", {}),
    }
    return f"""你是酒店推荐助手。请根据用户旅行需求推荐住宿候选，不要调用或假装拥有实时 OTA 房价。

要求：
- 只推荐适合游客预订的酒店/客栈/民宿品牌或住宿区域，不推荐大学宿舍、招待所、内部住宿。
- 价格必须是“参考区间”，并标记 price_is_estimated=true。
- mid-range 不要推荐明显低端的 100 元/晚民宿作为主推荐。
- reason 写给游客看，重点说明所在片区、去主要景点是否方便、周边餐饮/夜游/亲子/拍照等真实体验价值。
- reason 不要写“匹配中档住宿偏好”这类系统内部话术，不要堆砌泛泛形容词。
- 只返回 JSON。

上下文：
{to_json(context)}

返回：
{{
  "hotels": [
    {{
      "id": "llm_hotel_1",
      "name": "酒店名或住宿区域",
      "address": "所在区域",
      "type": "酒店",
      "price_estimate": "参考区间",
      "budget_price_per_room": 350,
      "price_is_estimated": true,
      "rating": 0,
      "reason": "匹配理由",
      "source": "llm_hotel"
    }}
  ]
}}"""


def _tool_result_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "weather_days": len((state.get("weather_data") or {}).get("forecast", []) or []),
        "attraction_count": len(state.get("attraction_candidates", []) or []),
        "food_count": len(state.get("food_candidates", []) or []),
        "hotel_count": len(state.get("hotel_options", []) or []),
        "transport_ready": bool(state.get("intercity_transport")),
        "sample_attractions": [item.get("name") for item in (state.get("attraction_candidates", []) or [])[:8]],
        "sample_foods": [item.get("name") for item in (state.get("food_candidates", []) or [])[:6]],
        "sample_hotels": [item.get("name") for item in (state.get("hotel_options", []) or [])[:4]],
    }


def _weather_context(state: Dict[str, Any]) -> Dict[str, Any]:
    forecasts = ((state.get("weather_data") or {}).get("forecast", []) or [])[: int(state.get("days", 3) or 3)]
    return {
        "forecasts": [
            {
                "date": item.get("date", ""),
                "condition": item.get("condition", ""),
                "temperature": item.get("temperature", {}),
            }
            for item in forecasts
        ],
        "impacts": state.get("weather_impacts", []) or [],
    }


def _top_items(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    keys = (
        "id",
        "name",
        "address",
        "type",
        "rating",
        "price",
        "avg_cost",
        "price_estimate",
        "budget_price_per_room",
        "price_is_estimated",
        "price_source",
        "price_confidence",
        "price_unit",
        "price_note",
        "reason",
        "opening_hours",
        "lat",
        "lng",
        "source",
    )
    result: List[Dict[str, Any]] = []
    for item in (items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        slim = {key: item.get(key) for key in keys if item.get(key) not in (None, "", [], {})}
        if slim:
            result.append(slim)
    return result
