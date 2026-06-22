from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, List

from app.core.config import settings
from app.mcp_tools.base import MCPToolProvider, run_async_sync
from app.mcp_tools.sse_client import MCPSSEServerConfig, call_mcp_sse_tool
from app.services.runtime_config import get_map_api_key, get_runtime_setting


logger = logging.getLogger(__name__)


class AMapSSEMCPProvider(MCPToolProvider):
    """AMap provider backed by the official remote MCP SSE service."""

    provider_name = "amap_mcp_sse"

    DEFAULT_TOOLS = {
        "text_search": "maps_text_search",
        "around_search": "maps_around_search",
        "detail_search": "maps_search_detail",
        "weather": "maps_weather",
        "walking": "maps_direction_walking",
        "bicycling": "maps_direction_bicycling",
        "driving": "maps_direction_driving",
        "transit": "maps_direction_transit_integrated",
        "distance": "maps_distance",
    }

    def __init__(self):
        self.tool_names = {**self.DEFAULT_TOOLS, **self._parse_tool_overrides(settings.AMAP_MCP_TOOL_OVERRIDES)}

    @staticmethod
    def is_enabled() -> bool:
        return bool((get_runtime_setting("map.amap_mcp.sse_url") or settings.AMAP_MCP_SSE_URL or "").strip())

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if tool_name == "geocode_pois":
            return self._search_pois(arguments)
        if tool_name == "plan_route":
            return self._plan_route(arguments)
        if tool_name == "get_weather_forecast":
            return self._get_weather(arguments)
        raise ValueError(f"Unsupported AMap SSE MCP tool: {tool_name}")

    def _search_pois(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        payload = {
            "keywords": arguments["keyword"],
            "city": arguments.get("city", ""),
        }
        raw = self._call_amap_tool("text_search", payload)
        items = self._extract_items(raw, ("pois", "items", "results", "data", "list"))
        return [self._normalize_poi(item) for item in items][: int(arguments.get("size") or 10)]

    def _plan_route(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        mode = str(arguments.get("mode") or "driving").lower()
        tool_key = {
            "walk": "walking",
            "walking": "walking",
            "bike": "bicycling",
            "bicycling": "bicycling",
            "transit": "transit",
            "bus": "transit",
            "driving": "driving",
            "drive": "driving",
        }.get(mode, "driving")

        payload = {
            "origin": arguments["origin"],
            "destination": arguments["destination"],
        }
        if tool_key == "transit":
            if arguments.get("city"):
                payload["city"] = arguments["city"]
            if arguments.get("cityd"):
                payload["cityd"] = arguments["cityd"]

        raw = self._call_amap_tool(tool_key, payload)
        return self._normalize_route(raw)

    def _get_weather(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        raw = self._call_amap_tool("weather", {"city": arguments["city"]})
        normalized = self._unwrap_payload(raw)
        forecasts = self._extract_items(normalized, ("forecasts", "forecast", "casts", "data", "list"))
        return {
            "city": self._pick_first(normalized, ("city", "province", "name")) or arguments["city"],
            "report_time": self._pick_first(normalized, ("reporttime", "report_time", "update_time")) or "",
            "forecast": [self._normalize_forecast(item) for item in forecasts][: int(arguments.get("days") or 3)],
        }

    def _call_amap_tool(self, tool_key: str, arguments: Dict[str, Any]) -> Any:
        tool_name = self.tool_names[tool_key]
        result = run_async_sync(call_mcp_sse_tool(self._build_config(), tool_name, arguments))
        return self._normalize_mcp_result(result)

    def _normalize_mcp_result(self, result: Any) -> Any:
        if isinstance(result, dict) and "content" in result:
            content = result.get("content")
            if isinstance(content, list):
                if len(content) == 1:
                    return self._normalize_content_block(content[0])
                return [self._normalize_content_block(item) for item in content]
            return content
        return result

    def _normalize_content_block(self, block: Any) -> Any:
        if isinstance(block, dict):
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                return self._parse_text_payload(block["text"])
            if "json" in block:
                return block["json"]
            if "data" in block:
                return block["data"]
        return block

    def _parse_text_payload(self, text: str) -> Any:
        text = text.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            json_match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
        return {"text": text}

    def _unwrap_payload(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, list):
            if len(payload) == 1:
                return self._unwrap_payload(payload[0])
            return {"items": [item for item in payload if isinstance(item, dict)]}
        if isinstance(payload, dict):
            for key in ("result", "data", "body"):
                value = payload.get(key)
                if isinstance(value, dict):
                    return value
            return payload
        return {}

    def _extract_items(self, payload: Any, keys: Iterable[str]) -> List[Dict[str, Any]]:
        normalized = self._unwrap_payload(payload)
        for key in keys:
            value = normalized.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = self._extract_items(value, keys)
                if nested:
                    return nested
        if any(key in normalized for key in ("id", "name", "location")):
            return [normalized]
        return []

    def _normalize_poi(self, item: Dict[str, Any], poi_type: str | None = None) -> Dict[str, Any]:
        lng, lat = self._parse_location(self._pick_first(item, ("location", "lnglat", "coordinate")))
        biz_ext = item.get("biz_ext") if isinstance(item.get("biz_ext"), dict) else {}
        photos = item.get("photos") if isinstance(item.get("photos"), list) else []
        image_url = photos[0].get("url") if photos and isinstance(photos[0], dict) else ""
        type_text = poi_type or str(self._pick_first(item, ("type", "typecode")) or "")
        price = str(self._pick_first(biz_ext, ("cost", "price")) or "")
        price_meta = self._price_metadata(price, type_text)
        return {
            "id": str(self._pick_first(item, ("id", "poiid", "poi_id", "uid")) or ""),
            "name": str(self._pick_first(item, ("name", "title")) or ""),
            "lat": lat,
            "lng": lng,
            "address": str(self._pick_first(item, ("address", "addr", "formatted_address")) or ""),
            "type": type_text,
            "rating": self._safe_float(self._pick_first(biz_ext, ("rating", "score"))),
            "price": price,
            **price_meta,
            "description": str(self._pick_first(item, ("description", "text")) or ""),
            "opening_hours": str(self._pick_first(biz_ext, ("opentime", "opening_hours")) or ""),
            "image_url": image_url or None,
            "best_time": "",
            "tips": "",
            "source": "amap_mcp_sse",
            "raw": item,
        }

    def _price_metadata(self, price: str, poi_type: str) -> Dict[str, Any]:
        if not str(price or "").strip():
            return {
                "avg_cost": 0,
                "price_source": "",
                "price_confidence": "unknown",
                "price_note": "",
            }
        type_text = str(poi_type or "")
        if any(token in type_text for token in ("餐饮", "美食", "餐厅", "小吃", "咖啡")):
            note = "高德地点参考人均消费，实际价格会随门店、时段和点单变化。"
            unit = "per_person"
        elif any(token in type_text for token in ("风景名胜", "景点", "博物", "展览", "公园")):
            note = "高德地点参考消费信息，不保证等同景区实时门票。"
            unit = "reference"
        elif any(token in type_text for token in ("酒店", "住宿", "宾馆", "旅馆")):
            note = "高德地点消费信息不能代表酒店实时房价，请以预订平台为准。"
            unit = "reference"
        else:
            note = "高德地点参考消费信息，实际价格可能波动。"
            unit = "reference"
        return {
            "avg_cost": int(self._safe_float(price)),
            "price_source": "amap_biz_ext_cost",
            "price_confidence": "reference",
            "price_unit": unit,
            "price_note": note,
        }

    def _normalize_route(self, payload: Any) -> Dict[str, Any]:
        item = self._unwrap_payload(payload)
        paths = item.get("paths") if isinstance(item.get("paths"), list) else []
        transits = item.get("transits") if isinstance(item.get("transits"), list) else []
        first_path = paths[0] if paths and isinstance(paths[0], dict) else {}
        first_transit = transits[0] if transits and isinstance(transits[0], dict) else {}
        route = first_path or first_transit or item
        return {
            "distance": self._safe_float(self._pick_first(route, ("distance", "cost_distance"))),
            "duration": self._safe_float(self._pick_first(route, ("duration", "cost_duration"))),
            "steps": self._pick_first(route, ("steps", "segments")) or [],
            "toll": self._safe_float(self._pick_first(route, ("toll", "tolls"))),
            "traffic_lights": int(self._safe_float(self._pick_first(route, ("traffic_lights", "trafficLights")))),
            "source": "amap_mcp_sse",
            "raw": payload,
        }

    def _normalize_forecast(self, item: Dict[str, Any]) -> Dict[str, Any]:
        day_temp = self._safe_float(self._pick_first(item, ("daytemp", "day_temp", "max_temp")))
        night_temp = self._safe_float(self._pick_first(item, ("nighttemp", "night_temp", "min_temp")))
        return {
            "date": str(self._pick_first(item, ("date", "day")) or ""),
            "condition": str(self._pick_first(item, ("dayweather", "weather", "condition")) or ""),
            "day_condition": str(self._pick_first(item, ("dayweather", "day_condition", "condition")) or ""),
            "night_condition": str(self._pick_first(item, ("nightweather", "night_condition", "condition")) or ""),
            "temperature": {
                "min": night_temp,
                "max": day_temp,
                "avg": round((day_temp + night_temp) / 2, 1) if day_temp or night_temp else 0,
            },
            "humidity": self._safe_float(self._pick_first(item, ("humidity",))),
            "wind_speed": 0,
            "day_wind_direction": str(self._pick_first(item, ("daywind", "day_wind_direction")) or ""),
            "night_wind_direction": str(self._pick_first(item, ("nightwind", "night_wind_direction")) or ""),
            "day_wind_power": str(self._pick_first(item, ("daypower", "day_wind_power")) or ""),
            "night_wind_power": str(self._pick_first(item, ("nightpower", "night_wind_power")) or ""),
            "icon": "unknown",
        }

    def _build_config(self) -> MCPSSEServerConfig:
        sse_url = (get_runtime_setting("map.amap_mcp.sse_url") or settings.AMAP_MCP_SSE_URL or "").strip()
        if not sse_url:
            raise RuntimeError("AMAP_MCP_SSE_URL 未配置，无法调用高德 MCP SSE")
        message_url = get_runtime_setting("map.amap_mcp.message_url") or settings.AMAP_MCP_SSE_MESSAGE_URL
        return MCPSSEServerConfig(
            sse_url=sse_url,
            message_url=message_url,
            headers=self._build_headers(),
            connect_timeout=settings.AMAP_MCP_CONNECT_TIMEOUT,
            request_timeout=settings.AMAP_MCP_REQUEST_TIMEOUT,
        )

    @staticmethod
    def _build_headers() -> Dict[str, str]:
        headers: Dict[str, str] = {}
        token = (
            get_runtime_setting("map.amap_mcp.api_key")
            or settings.AMAP_MCP_API_KEY
            or get_map_api_key("amap")
            or ""
        ).strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if settings.AMAP_MCP_HEADERS:
            try:
                extra = json.loads(settings.AMAP_MCP_HEADERS)
                if isinstance(extra, dict):
                    headers.update({str(key): str(value) for key, value in extra.items()})
            except json.JSONDecodeError:
                logger.warning("AMAP_MCP_HEADERS is not valid JSON; ignored")
        return headers

    @staticmethod
    def _parse_tool_overrides(raw: str | None) -> Dict[str, str]:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("AMAP_MCP_TOOL_OVERRIDES is not valid JSON; ignored")
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items() if value}

    @staticmethod
    def _parse_location(value: Any) -> tuple[float, float]:
        if isinstance(value, str):
            parts = value.split(",")
            if len(parts) >= 2:
                return AMapSSEMCPProvider._safe_float(parts[0]), AMapSSEMCPProvider._safe_float(parts[1])
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return AMapSSEMCPProvider._safe_float(value[0]), AMapSSEMCPProvider._safe_float(value[1])
        if isinstance(value, dict):
            lng = AMapSSEMCPProvider._safe_float(value.get("lng") or value.get("lon") or value.get("longitude"))
            lat = AMapSSEMCPProvider._safe_float(value.get("lat") or value.get("latitude"))
            return lng, lat
        return 0.0, 0.0

    @staticmethod
    def _pick_first(item: Dict[str, Any], keys: Iterable[str]) -> Any:
        for key in keys:
            value = item.get(key)
            if value not in (None, "", []):
                return value
        return None

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return float(value)
            matched = re.search(r"-?\d+(?:\.\d+)?", str(value))
            return float(matched.group()) if matched else default
        except Exception:
            return default
