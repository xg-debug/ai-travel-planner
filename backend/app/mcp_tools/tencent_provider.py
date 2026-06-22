from __future__ import annotations

from typing import Any, Dict

from app.mcp_tools.base import MCPToolProvider
from app.services.tencent_map_service import calculate_route, search_pois


class TencentMapMCPProvider(MCPToolProvider):
    """Tencent Location Service provider for POI and route tools."""

    provider_name = "tencent"

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if tool_name == "geocode_pois":
            return search_pois(
                arguments["keyword"],
                arguments["city"],
                arguments.get("page", 1),
                arguments.get("size", 10),
            )
        if tool_name == "plan_route":
            return calculate_route(
                arguments["origin"],
                arguments["destination"],
                arguments.get("mode", "driving"),
            )
        if tool_name == "get_weather_forecast":
            raise RuntimeError("腾讯位置服务暂未提供天气能力，请配置高德地图用于天气查询")
        raise ValueError(f"Unsupported Tencent MCP tool: {tool_name}")
