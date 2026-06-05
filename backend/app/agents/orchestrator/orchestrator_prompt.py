from __future__ import annotations

import json
from typing import Any, Dict, List


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def build_orchestrator_prompt(
    state: Dict[str, Any],
    memory: Dict[str, Any],
    observations: List[Dict[str, Any]],
    *,
    step_index: int,
    last_error: str = "",
) -> str:
    return f"""
你是旅行规划系统的主控智能体。你不是固定流水线执行器，而是负责思考、决定下一步调用什么工具、何时补查信息、何时进入最终整合的旅行规划专家。

你必须基于真实工具结果进行规划。工具和子智能体只提供事实、候选、评分、路线、预算、审查意见；最终取舍和行程整合由你完成。

【用户需求】
{_json({
    "city": state.get("city", ""),
    "departure_city": state.get("departure_city", ""),
    "days": state.get("days", 1),
    "travelers": state.get("travelers", 1),
    "budget": state.get("budget", "中等"),
    "budget_amount": state.get("budget_amount", 0),
    "preferences": state.get("preferences", []) or [],
    "start_date": state.get("start_date"),
    "outbound_departure_datetime": state.get("outbound_departure_datetime"),
    "return_arrival_datetime": state.get("return_arrival_datetime"),
    "query": state.get("query", ""),
})}

【当前工作记忆】
{_json(memory)}

【最近工具观察】
{_json(observations[-6:])}

【上一步错误】
{last_error or "无"}

【可调用动作】
1. plan_search_strategy：让 Planner 子智能体理解需求并给出搜索策略。
2. get_weather：获取天气和天气影响。
3. search_attractions：搜索真实景点/街区/体验候选。args 可包含 queries。
4. search_foods：搜索真实餐饮候选。args 可包含 queries。
5. search_hotels：搜索真实酒店候选。args 可包含 queries。
6. score_candidates：根据偏好、天气、预算、POI 完整度为候选排序。
7. evaluate_transport：评估候选之间的动线和通勤。
8. enrich_poi：为已有草案补全坐标、图片和 POI 细节。
9. review_itinerary：调用 reviewer 子智能体审查并给出修补参考。
10. estimate_budget：估算预算。
11. build_risk_notices：生成风险和避坑提醒。
12. finalize：当信息足够时进入最终整合。

【决策要求】
- 自主决定下一步，不要机械按列表顺序调用。
- 但最终行程必须尽量使用真实景点、真实餐饮、真实酒店和天气信息。
- 如果缺少景点/餐饮/酒店/天气中的关键事实，不要 finalize。
- 如果已有足够候选和天气，优先进入评分、动线、最终整合。
- 不要编造工具名称。action 必须从上面的动作中选择。
- 当前是第 {step_index + 1} 轮，最多需要在有限轮数内收敛。

【返回格式】
只返回一个 JSON 对象，不要 Markdown，不要解释。格式：
{{
  "thought": "一句话说明为什么选择这个动作",
  "action": "动作名",
  "args": {{}}
}}

如果 action 是 finalize，可以额外包含 final 字段；如果你不能一次性生成 final，也可以只返回 finalize，系统会再要求你输出最终结构化行程。
"""


def build_final_plan_prompt(
    state: Dict[str, Any],
    memory: Dict[str, Any],
    observations: List[Dict[str, Any]],
    *,
    repair_error: str = "",
    previous_output: Any = None,
) -> str:
    context = {
        "request": {
            "city": state.get("city", ""),
            "departure_city": state.get("departure_city", ""),
            "days": state.get("days", 1),
            "travelers": state.get("travelers", 1),
            "budget": state.get("budget", "中等"),
            "budget_amount": state.get("budget_amount", 0),
            "preferences": state.get("preferences", []) or [],
            "start_date": state.get("start_date"),
            "outbound_departure_datetime": state.get("outbound_departure_datetime"),
            "return_arrival_datetime": state.get("return_arrival_datetime"),
            "query": state.get("query", ""),
        },
        "query_plan": state.get("query_plan", {}),
        "weather": state.get("weather_data", {}),
        "weather_impacts": state.get("weather_impacts", []) or [],
        "attractions": _top_items(
            state.get("scored_attractions") or state.get("attraction_candidates") or [],
            max(8, int(state.get("days", 1) or 1) * 3),
        ),
        "foods": _top_items(
            state.get("scored_foods") or state.get("food_candidates") or [],
            max(8, int(state.get("days", 1) or 1) * 2),
        ),
        "hotels": _top_items(state.get("scored_hotels") or state.get("hotel_options") or [], 5),
        "transport_plan": state.get("transport_plan", {}),
        "intercity_transport": state.get("intercity_transport", {}),
        "estimated_budget": state.get("estimated_budget", {}),
        "risk_notices": state.get("risk_notices", []) or [],
        "memory": memory,
        "observations": observations[-5:],
    }

    return f"""
你是旅行规划系统的最终整合智能体。请基于下方真实工具结果，生成详细、可执行、结构化的多日行程。

【重要约束】
- 必须优先使用候选中的真实地点，不要凭空编造地点。
- 活动的 location 必须是候选列表里的真实 POI 名称，不能写成“探索/攀登/漫步/扫街/打卡...”这类活动文案。
- 如果要表达玩法和体验，把文案写在 title 或 description；location 只放真实地图地点名。
- 能确定候选 id 时，在活动里带上 source_id 和 source；坐标已知时带上 coordinates。
- 不要在不必要的情况下重复安排同一个景点；多日行程应优先覆盖不同真实景点。
- budget_amount 是用户总预算硬上限；如果 budget_amount 大于 0，行程档次应接近该预算，估算总额尽量落在预算的 85%-100%，不能为了省钱明显低配。
- 同一天必须围绕同一区域或相邻区域安排，避免在城市东西两端来回跑。
- 每天活动顺序要按地理位置自然串联，餐饮优先选择靠近当天景点链路的候选。
- 晚餐必须优先靠近当天酒店或下午最后一个景点；如果当天入住海岛/远郊/新区，晚餐不能安排回主城区。
- 晚餐时间不能写死为 18:00，必须根据下午活动结束时间、夜间活动和返程交通动态安排；晚餐后如果仍有合理夜间体验，可以继续安排夜景、演出、夜市或轻量散步。
- 最后一天如果安排返程交通，返程交通是目的地行程的终止点；返程之后不能再安排目的地景点、餐厅、夜间活动或购物。
- 第一天 activities 必须包含从出发地到目的地的去程交通，并且目的地游玩活动只能安排在到达时间之后。
- 最后一天 activities 必须包含从目的地回出发地的返程交通，并且目的地活动必须安排在返程出发时间之前。
- 当天最后一站应便于返回 hotel_recommendation，避免晚上跨区长距离折返。
- 不要把“入住酒店/办理入住/返回酒店”写入 activities；酒店只写在 hotel_recommendation。
- 餐饮标题必须和时间一致：12:00 左右写午餐，15:00 左右写下午茶，18:00 左右写晚餐，不能同一时间安排多个活动。
- 每天安排 4 到 6 个活动，包含景点/体验和餐饮。
- 每天必须有 hotel_recommendation。
- 活动时间要合理，避免过密。
- 结合天气影响给出 weather_advice。
- description、tips、transportation 要具体实用。
- 所有内容使用简体中文。
- 只返回合法 JSON，不要 Markdown，不要代码块。

【上下文】
{_json(context)}

【修复要求】
{repair_error or "无"}

【上一次无效输出】
{_json(previous_output) if previous_output is not None else "无"}

【返回 JSON 结构】
{{
  "itinerary": [
    {{
      "day": 1,
      "date": "YYYY-MM-DD 或 null",
      "theme": "当天主题",
      "summary": "当天概览",
      "weather_advice": "结合天气的安排建议",
      "hotel_recommendation": {{
        "name": "酒店名",
        "price_estimate": "价格或空字符串",
        "address": "地址",
        "reason": "为什么适合本行程",
        "source": "候选来源，可为空",
        "source_id": "候选 id，可为空",
        "coordinates": {{"lat": 22.0, "lng": 113.0}}
      }},
      "activities": [
        {{
          "time": "09:30-11:30",
          "title": "活动标题",
          "description": "活动说明",
          "type": "景点游览/美食餐饮/休闲体验/交通衔接",
          "location": "真实地点名",
          "duration": 90,
          "cost_estimate": 0,
          "ticket_price": 0,
          "tips": "实用提示",
          "transportation": "从上一站或酒店出发的建议交通",
          "source": "候选来源，可为空",
          "source_id": "候选 id，可为空",
          "coordinates": {{"lat": 22.0, "lng": 113.0}}
        }}
      ]
    }}
  ],
  "final_output": "一段 Markdown 文本，概括行程亮点、路线策略、预算和注意事项"
}}
"""


def _top_items(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for item in list(items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "address": item.get("address", ""),
                "type": item.get("type", ""),
                "rating": item.get("rating", 0),
                "price": item.get("price", ""),
                "opening_hours": item.get("opening_hours", ""),
                "lat": item.get("lat"),
                "lng": item.get("lng"),
                "source": item.get("source", ""),
                "score": item.get("score"),
                "reason": item.get("reason", ""),
            }
        )
    return result
