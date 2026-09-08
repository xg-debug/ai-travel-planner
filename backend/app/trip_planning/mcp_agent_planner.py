from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List

from app.core.config import settings
from app.core.llm import LLMFactory
from app.mcp_tools.base import run_async_sync
from app.services.runtime_config import get_map_api_key, is_present_secret
from app.trip_planning.budget import budget_node
from app.trip_planning.harness import EventSink
from app.trip_planning.itinerary import normalize_itinerary, summary_node
from app.trip_planning.risk_notices import risk_notice_node
from app.trip_planning.utils import extract_json_block
from app.trip_planning.weather_impact import weather_impact_service

logger = logging.getLogger(__name__)

AMAP_TOOL_NAMES = {
    "maps_text_search",
    "maps_weather",
    "maps_direction_walking",
    "maps_direction_driving",
    "maps_direction_transit_integrated",
    "maps_geo",
    "maps_search_detail",
    "maps_around_search",
    "maps_direction_bicycling",
}

_amap_mcp_client: Any = None
_amap_mcp_tools: List[Any] | None = None
_amap_mcp_tools_lock = threading.Lock()


async def get_amap_mcp_tools() -> List[Any]:
    """Load AMap MCP tools once and share them across planner runs."""
    global _amap_mcp_client, _amap_mcp_tools

    if _amap_mcp_tools is not None:
        return _amap_mcp_tools

    with _amap_mcp_tools_lock:
        if _amap_mcp_tools is not None:
            return _amap_mcp_tools

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except Exception as exc:  # pragma: no cover - environment configuration
            raise RuntimeError("缺少 langchain-mcp-adapters 依赖，请先安装 backend/requirements.txt") from exc

        from app.mcp_tools.amap_provider import mcp_connection
        url, headers = mcp_connection()
        _amap_mcp_client = MultiServerMCPClient({"amap": {
            "url": url, "headers": headers, "transport": "streamable_http",
        }})
        tools = await _amap_mcp_client.get_tools()
        selected = [tool for tool in tools if _is_amap_tool_allowed(getattr(tool, "name", ""))]
        if not selected:
            available = ", ".join(getattr(tool, "name", "") for tool in tools) or "none"
            raise RuntimeError(f"高德 MCP 工具加载成功但未找到允许的工具，可用工具：{available}")

        _amap_mcp_tools = selected
        logger.info("AMap MCP tools loaded: %s", ", ".join(getattr(tool, "name", "") for tool in selected))
        return selected


class MCPAgentTripPlanner:
    """Trip planner that lets a LangGraph ReAct agent call AMap MCP tools directly."""

    def __init__(self) -> None:
        self._tool_names: List[str] = []

    def run(
        self,
        state: Dict[str, Any],
        emit: EventSink | None = None,
    ) -> Dict[str, Any]:
        return run_async_sync(self.arun(state, emit=emit))

    async def arun(
        self,
        state: Dict[str, Any],
        emit: EventSink | None = None,
    ) -> Dict[str, Any]:
        agent = await self._compiled_agent()
        query = self._build_user_query(state)
        logger.info("MCP agent trip planning started city=%s days=%s", state.get("city"), state.get("days"))
        content, tool_trace = await self._run_agent(agent, query, emit)
        parsed = extract_json_block(content)
        if not isinstance(parsed, dict):
            logger.warning("MCP agent returned non-json response: %s", content[:500])
            raise RuntimeError("高德 MCP Agent 未返回可解析的 JSON 行程")
        _validate_tool_trace(tool_trace)
        if emit:
            emit(
                "itinerary_synthesis",
                "地图研究已完成，正在编排行程并检查每天的节奏",
                {"tool_calls": len(tool_trace)},
            )
        result = self._postprocess(parsed, state, tool_trace)
        if emit:
            emit(
                "itinerary_review",
                "已检查地点真实性、重复安排和每日活动密度",
                {
                    "days": len(result.get("plan") or []),
                    "activities": sum(len(day.get("activities") or []) for day in result.get("plan") or []),
                },
            )
            emit("budget_estimation", "已按人数、间夜和活动参考价完成预算估算")
            emit("risk_notices", "已结合天气与路线生成出行提醒")
        return result

    async def _run_agent(
        self,
        agent: Any,
        query: str,
        emit: EventSink | None,
    ) -> tuple[str, List[Dict[str, Any]]]:
        last_content = ""
        scheduled_calls: Dict[str, Dict[str, Any]] = {}
        completed_call_ids: set[str] = set()
        tool_trace: List[Dict[str, Any]] = []

        async for update in agent.astream(
            {"messages": [{"role": "user", "content": query}]},
            config={"recursion_limit": 18},
            stream_mode="updates",
        ):
            for message in _messages_from_update(update):
                content = _message_content(message)
                message_type = str(getattr(message, "type", "") or "")
                if message_type in {"ai", "assistant"} and content:
                    last_content = content
                for call in getattr(message, "tool_calls", None) or []:
                    call_id = str(call.get("id") or "")
                    if call_id and call_id in scheduled_calls:
                        continue
                    name = str(call.get("name") or "")
                    args = call.get("args") if isinstance(call.get("args"), dict) else {}
                    scheduled_calls[call_id] = {"name": name, "args": args}
                    if emit:
                        step, status_message = _tool_status(name, args, completed=False)
                        emit(step, status_message, {"tool": _short_tool_name(name)})
                if message_type == "tool":
                    call_id = str(getattr(message, "tool_call_id", "") or "")
                    if call_id and call_id in completed_call_ids:
                        continue
                    if call_id:
                        completed_call_ids.add(call_id)
                    scheduled = scheduled_calls.get(call_id, {})
                    name = str(getattr(message, "name", "") or scheduled.get("name") or "unknown")
                    args = scheduled.get("args") if isinstance(scheduled.get("args"), dict) else {}
                    trace_item = {
                        "tool": _short_tool_name(name),
                        "step": _tool_status(name, args, completed=True)[0],
                        "ok": not _tool_message_failed(content),
                    }
                    tool_trace.append(trace_item)
                    if emit:
                        step, status_message = _tool_status(name, args, completed=True)
                        emit(step, status_message, trace_item)

        return last_content, tool_trace

    async def _compiled_agent(self):
        from langgraph.prebuilt import create_react_agent

        tools = await get_amap_mcp_tools()
        self._tool_names = [str(getattr(tool, "name", "")) for tool in tools if getattr(tool, "name", "")]
        llm = LLMFactory.create_llm(
            temperature=0.25,
            max_tokens=max(settings.LLM_MAX_TOKENS, 4500),
            request_timeout=max(settings.LLM_REQUEST_TIMEOUT_SECONDS, 120),
            max_retries=settings.LLM_MAX_RETRIES,
        )
        return create_react_agent(
            model=llm,
            tools=tools,
            prompt=self._system_prompt(),
            name="amap_trip_planner",
        )

    def _system_prompt(self) -> str:
        tool_lines = "\n".join(f"- {name}" for name in self._tool_names) or "- 高德地图 MCP 工具"
        return f"""你是一个会自主调用高德地图 MCP 工具的智能旅行规划 Agent。

你可以使用这些工具：
{tool_lines}

工作方式：
1. 必须主动调用高德 MCP 工具查询真实地点，不要凭空编造景点、酒店、餐厅、天气或路线。
2. 用 maps_text_search 搜索景点、餐厅、美食街、酒店和住宿区域；关键词要结合城市、偏好、预算档位和用户额外要求。
3. 用 maps_weather 查询目的地天气。
4. 用 maps_direction_walking、maps_direction_driving、maps_direction_transit_integrated 评估相邻地点动线；按用户交通偏好选择路线工具。
5. 酒店价格可以使用地图返回的 cost/price/参考消费或搜索摘要中的价格线索，但必须标记为参考价，不要声称是实时预订价。
6. 预算需要保守估算：餐饮按人均，酒店按每间夜，门票/活动按人头；无法确认价格时给出合理参考并说明置信度。
7. 每天安排 2-4 个主要活动，餐饮要顺路，避免多天重复同一核心景点，避免明显跨区折返。

最终只能输出一个 JSON 对象，不要输出 Markdown。JSON schema：
{{
  "final_output": "面向用户的简短行程总结",
  "weather_data": {{
    "city": "城市",
    "report_time": "更新时间",
    "forecast": [
      {{
        "date": "YYYY-MM-DD",
        "condition": "天气",
        "day_condition": "白天天气",
        "night_condition": "夜间天气",
        "temperature": {{"min": 0, "max": 0, "avg": 0}},
        "humidity": 0,
        "wind_speed": 0,
        "day_wind_direction": "",
        "night_wind_direction": "",
        "day_wind_power": "",
        "night_wind_power": "",
        "icon": "unknown"
      }}
    ]
  }},
  "attraction_candidates": [
    {{
      "id": "poi id",
      "name": "地点名",
      "lat": 0,
      "lng": 0,
      "address": "地址",
      "type": "景点类型",
      "rating": 0,
      "price": "参考价格",
      "avg_cost": 0,
      "price_confidence": "reference",
      "description": "推荐理由",
      "opening_hours": "",
      "source": "amap_mcp_agent"
    }}
  ],
  "food_candidates": [
    {{
      "id": "poi id",
      "name": "餐厅名",
      "lat": 0,
      "lng": 0,
      "address": "地址",
      "type": "美食餐饮",
      "rating": 0,
      "price": "参考价格",
      "avg_cost": 0,
      "price_confidence": "reference",
      "description": "推荐理由",
      "opening_hours": "",
      "source": "amap_mcp_agent"
    }}
  ],
  "hotel_options": [
    {{
      "id": "poi id",
      "name": "酒店名或住宿区域",
      "lat": 0,
      "lng": 0,
      "address": "地址",
      "type": "酒店",
      "rating": 0,
      "price": "参考价格",
      "price_estimate": "参考价格",
      "budget_price_per_room": 0,
      "price_is_estimated": true,
      "price_confidence": "reference",
      "price_note": "地图参考价，非实时预订价",
      "reason": "为什么适合本次路线",
      "source": "amap_mcp_agent"
    }}
  ],
  "recommendations": [
    {{"title": "推荐标题", "type": "景点/美食/住宿", "items": []}}
  ],
  "plan": [
    {{
      "day": 1,
      "date": "YYYY-MM-DD",
      "theme": "当天主题",
      "summary": "当天概览",
      "weather_advice": "天气建议",
      "hotel_recommendation": {{
        "name": "酒店名",
        "address": "地址",
        "price_estimate": "参考价格",
        "budget_price_per_room": 0,
        "price_is_estimated": true,
        "price_confidence": "reference",
        "price_note": "地图参考价，非实时预订价",
        "reason": "住宿理由",
        "coordinates": {{"lat": 0, "lng": 0}}
      }},
      "activities": [
        {{
          "time": "09:30-11:30",
          "title": "活动标题",
          "type": "景点游览/美食餐饮/休闲体验/交通衔接",
          "location": "真实地点名",
          "description": "为什么安排这里",
          "duration": 90,
          "cost_estimate": 0,
          "ticket_price": 0,
          "avg_cost": 0,
          "tips": "游玩提醒",
          "transportation": "到下一站的真实路线摘要",
          "coordinates": {{"lat": 0, "lng": 0}},
          "source": "amap_mcp_agent",
          "source_id": "poi id",
          "price_confidence": "reference"
        }}
      ]
    }}
  ]
}}"""

    def _build_user_query(self, state: Dict[str, Any]) -> str:
        preferences = "、".join(str(item) for item in state.get("preferences") or []) or "城市经典体验"
        return f"""请直接调用高德地图 MCP 工具，为用户生成一份可执行旅行规划。

用户需求：
- 出发城市：{state.get("departure_city") or "未填写"}
- 目的地：{state.get("city")}
- 旅行天数：{state.get("days")} 天
- 出发时间：{state.get("outbound_departure_datetime") or state.get("start_date")}
- 返程到达：{state.get("return_arrival_datetime") or "未填写"}
- 出行人数：{state.get("travelers", 1)}
- 兴趣偏好：{preferences}
- 住宿偏好：{state.get("accommodation_preference", "mid-range")}
- 预算总额：{state.get("budget_amount") or "未填写"} 元
- 用户补充需求：{state.get("query") or "无"}

请自主选择工具查询：
1. 天气；
2. 至少 {max(8, int(state.get("days") or 1) * 4)} 个景点/体验候选；
3. 至少 {max(6, int(state.get("days") or 1) * 3)} 个餐厅/美食候选；
4. 至少 3 个酒店或住宿区域；
5. 每天相邻地点之间的步行/驾车/公交路线摘要。

请输出严格 JSON，字段必须符合系统提示中的 schema。"""

    def _postprocess(
        self,
        parsed: Dict[str, Any],
        state: Dict[str, Any],
        tool_trace: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {**state}
        result["attraction_candidates"] = _normalize_candidates(parsed.get("attraction_candidates"), "景点")
        result["food_candidates"] = _normalize_candidates(parsed.get("food_candidates"), "美食餐饮")
        result["hotel_options"] = _normalize_hotels(parsed.get("hotel_options"))
        result["recommendations"] = _normalize_recommendations(parsed.get("recommendations"), result)
        result["weather_data"] = _normalize_weather(parsed.get("weather_data"), state)

        raw_plan = parsed.get("plan") or parsed.get("itinerary") or []
        plan = normalize_itinerary(raw_plan if isinstance(raw_plan, list) else [], result)
        if not any(day.get("activities") for day in plan):
            raise RuntimeError("高德 MCP Agent 未生成可用每日行程")
        result["plan"] = _attach_hotel_defaults(plan, result["hotel_options"])
        result["final_output"] = str(parsed.get("final_output") or "").strip()
        result["poi_data"] = _build_poi_data(result)

        result["weather_impacts"] = weather_impact_service.build_impacts(
            result.get("weather_data") or {},
            state.get("start_date"),
            int(state.get("days") or 1),
        )
        result.update(budget_node(result))
        result.update(risk_notice_node(result))
        if not result.get("final_output"):
            result.update(summary_node(result))
        result["quality_score"] = _quality_score(result, tool_trace)
        result["agent_run"] = {
            "planner": "amap_react",
            "tool_calls": tool_trace,
            "tool_call_count": len(tool_trace),
        }
        return result


def _is_amap_tool_allowed(name: str) -> bool:
    short_name = name.split("__")[-1].split(".")[-1]
    if short_name in AMAP_TOOL_NAMES:
        return True
    return any(short_name.endswith(tool_name) for tool_name in AMAP_TOOL_NAMES)


def _last_message_content(result: Any) -> str:
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        return str(result or "")
    content = getattr(messages[-1], "content", messages[-1])
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content or "")


def _messages_from_update(value: Any) -> List[Any]:
    messages: List[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "messages" and isinstance(item, list):
                messages.extend(item)
            else:
                messages.extend(_messages_from_update(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            messages.extend(_messages_from_update(item))
    return messages


def _message_content(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            elif item not in (None, ""):
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content or "")


def _short_tool_name(name: str) -> str:
    return str(name or "").split("__")[-1].split(".")[-1]


def _tool_status(
    name: str,
    args: Dict[str, Any],
    completed: bool,
) -> tuple[str, str]:
    short_name = _short_tool_name(name)
    verb = "已获得" if completed else "正在查询"
    if "weather" in short_name:
        return "weather_lookup", f"{verb}目的地天气与出行条件"
    if "direction" in short_name:
        return "transport_planning", f"{verb}相邻地点的真实交通路线"
    query_text = " ".join(str(value) for value in args.values())
    if any(token in query_text for token in ("酒店", "住宿", "宾馆", "民宿")):
        return "hotel_search", f"{verb}适合本次预算和动线的住宿"
    if any(token in query_text for token in ("餐厅", "餐馆", "美食", "小吃", "咖啡")):
        return "food_search", f"{verb}沿途餐厅与本地风味"
    return "attraction_search", f"{verb}真实景点与旅行体验"


def _tool_message_failed(content: str) -> bool:
    lowered = content.lower()
    return any(token in lowered for token in ("error", "failed", "exception", "调用失败"))


def _validate_tool_trace(tool_trace: List[Dict[str, Any]]) -> None:
    successful = {
        str(item.get("tool") or "")
        for item in tool_trace
        if item.get("ok") is not False
    }
    if not successful:
        raise RuntimeError("地图 Agent 未完成任何有效工具调用，已阻止输出未经验证的行程")
    if not any("text_search" in name for name in successful):
        raise RuntimeError("地图 Agent 未完成地点检索，已阻止输出未经验证的地点")
    if not any("weather" in name for name in successful):
        raise RuntimeError("地图 Agent 未完成天气查询，无法生成可靠出行建议")


def _normalize_candidates(value: Any, default_type: str) -> List[Dict[str, Any]]:
    items = value if isinstance(value, list) else []
    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("title") or "").strip()
        if not name:
            continue
        lat, lng = _coordinates(item)
        normalized.append(
            {
                "id": str(item.get("id") or item.get("source_id") or item.get("poi_id") or f"amap_mcp_{index + 1}"),
                "name": name,
                "lat": lat,
                "lng": lng,
                "address": str(item.get("address") or ""),
                "type": str(item.get("type") or default_type),
                "rating": _safe_float(item.get("rating")),
                "price": str(item.get("price") or item.get("price_estimate") or ""),
                "avg_cost": int(_safe_float(item.get("avg_cost") or item.get("cost_estimate"))),
                "price_source": str(item.get("price_source") or "amap_mcp_agent"),
                "price_confidence": str(item.get("price_confidence") or "reference"),
                "price_unit": str(item.get("price_unit") or "reference"),
                "price_note": str(item.get("price_note") or "地图参考消费，实际价格可能变化。"),
                "description": str(item.get("description") or item.get("reason") or ""),
                "opening_hours": str(item.get("opening_hours") or ""),
                "best_time": str(item.get("best_time") or ""),
                "tips": str(item.get("tips") or ""),
                "image_url": item.get("image_url") or item.get("image"),
                "source": str(item.get("source") or "amap_mcp_agent"),
            }
        )
    return normalized


def _normalize_hotels(value: Any) -> List[Dict[str, Any]]:
    hotels = _normalize_candidates(value, "酒店")
    for hotel in hotels:
        hotel["price_estimate"] = hotel.get("price") or ""
        hotel["budget_price_per_room"] = int(_safe_float(hotel.get("budget_price_per_room") or hotel.get("avg_cost")))
        hotel["price_is_estimated"] = True
        hotel["reason"] = hotel.get("description") or "位置便于衔接主要景点和餐饮。"
        hotel["price_note"] = hotel.get("price_note") or "地图参考价，非实时预订价。"
    return hotels


def _normalize_recommendations(value: Any, result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(value, list) and value:
        return [item for item in value if isinstance(item, dict)]
    recommendations: List[Dict[str, Any]] = []
    if result.get("attraction_candidates"):
        recommendations.append(
            {
                "title": "景点推荐",
                "type": "景点",
                "items": result["attraction_candidates"][:10],
                "reason": "由高德 MCP Agent 根据偏好和真实地图查询结果筛选。",
            }
        )
    if result.get("food_candidates"):
        recommendations.append(
            {
                "title": "美食推荐",
                "type": "美食",
                "items": result["food_candidates"][:8],
                "reason": "由高德 MCP Agent 结合路线顺路性筛选。",
            }
        )
    return recommendations


def _normalize_weather(value: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    weather = value if isinstance(value, dict) else {}
    forecasts = weather.get("forecast") if isinstance(weather.get("forecast"), list) else []
    normalized = []
    for item in forecasts:
        if not isinstance(item, dict):
            continue
        temp = item.get("temperature") if isinstance(item.get("temperature"), dict) else {}
        normalized.append(
            {
                "date": str(item.get("date") or ""),
                "condition": str(item.get("condition") or item.get("day_condition") or ""),
                "day_condition": str(item.get("day_condition") or item.get("condition") or ""),
                "night_condition": str(item.get("night_condition") or item.get("condition") or ""),
                "temperature": {
                    "min": _safe_float(temp.get("min")),
                    "max": _safe_float(temp.get("max")),
                    "avg": _safe_float(temp.get("avg")),
                },
                "humidity": _safe_float(item.get("humidity")),
                "wind_speed": _safe_float(item.get("wind_speed")),
                "day_wind_direction": str(item.get("day_wind_direction") or ""),
                "night_wind_direction": str(item.get("night_wind_direction") or ""),
                "day_wind_power": str(item.get("day_wind_power") or ""),
                "night_wind_power": str(item.get("night_wind_power") or ""),
                "icon": str(item.get("icon") or "unknown"),
            }
        )
    return {
        "city": str(weather.get("city") or state.get("city") or ""),
        "report_time": str(weather.get("report_time") or ""),
        "forecast": normalized,
    }


def _attach_hotel_defaults(plan: List[Dict[str, Any]], hotels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for day in plan:
        hotel = day.get("hotel_recommendation")
        if isinstance(hotel, dict) and hotel.get("name"):
            hotel.setdefault("price_is_estimated", True)
            hotel.setdefault("price_confidence", "reference")
            hotel.setdefault("price_note", "地图参考价，非实时预订价。")
            continue
        if not hotels:
            continue
        selected = hotels[min(int(day.get("day") or 1) - 1, len(hotels) - 1)]
        replacement: Dict[str, Any] = {
            "name": selected.get("name", ""),
            "address": selected.get("address", ""),
            "price_estimate": selected.get("price_estimate") or selected.get("price") or "",
            "budget_price_per_room": selected.get("budget_price_per_room") or 0,
            "price_is_estimated": True,
            "price_confidence": "reference",
            "price_note": selected.get("price_note") or "地图参考价，非实时预订价。",
            "reason": selected.get("reason") or selected.get("description") or "",
        }
        if selected.get("lat") and selected.get("lng"):
            replacement["coordinates"] = {"lat": selected["lat"], "lng": selected["lng"]}
        day["hotel_recommendation"] = replacement
    return plan


def _build_poi_data(result: Dict[str, Any]) -> Dict[str, Any]:
    pois: Dict[str, Any] = {}
    for key in ("attraction_candidates", "food_candidates", "hotel_options"):
        for item in result.get(key) or []:
            name = str(item.get("name") or "").strip()
            if name:
                pois[name] = item
    return pois


def _coordinates(item: Dict[str, Any]) -> tuple[float, float]:
    coords = item.get("coordinates") if isinstance(item.get("coordinates"), dict) else {}
    lat = _safe_float(item.get("lat") or item.get("latitude") or coords.get("lat") or coords.get("latitude"))
    lng = _safe_float(item.get("lng") or item.get("lon") or item.get("longitude") or coords.get("lng") or coords.get("longitude"))
    location = item.get("location")
    if (not lat or not lng) and isinstance(location, str) and "," in location:
        left, right = location.split(",", 1)
        lng = _safe_float(left)
        lat = _safe_float(right)
    return lat, lng


def _safe_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        import re

        matched = re.search(r"-?\d+(?:\.\d+)?", str(value))
        return float(matched.group()) if matched else 0.0
    except Exception:
        return 0.0


def _quality_score(result: Dict[str, Any], tool_trace: List[Dict[str, Any]]) -> Dict[str, Any]:
    plan = result.get("plan") or []
    activities = [
        activity
        for day in plan
        for activity in day.get("activities", []) or []
        if isinstance(activity, dict)
    ]
    located = sum(1 for item in activities if (item.get("coordinates") or {}).get("lat") and (item.get("coordinates") or {}).get("lng"))
    successful_tools = [item for item in tool_trace if item.get("ok") is not False]
    route_calls = sum(1 for item in successful_tools if item.get("step") == "transport_planning")
    score = 68 + min(18, located * 2) + min(6, len(successful_tools)) + min(3, route_calls)
    return {
        "score": min(95, score),
        "located_activity_count": located,
        "activity_count": len(activities),
        "tool_call_count": len(tool_trace),
        "successful_tool_call_count": len(successful_tools),
        "route_call_count": route_calls,
        "review": "地图研究、行程编排和确定性预算/风险校验均已完成。",
    }


mcp_agent_trip_planner = MCPAgentTripPlanner()
