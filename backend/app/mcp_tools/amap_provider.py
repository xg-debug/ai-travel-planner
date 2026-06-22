from __future__ import annotations

from typing import Any, Dict

from app.mcp_tools.base import MCPToolProvider
from app.services.amap_service import calculate_route, get_weather_forecast, search_pois


class AMapMCPProvider(MCPToolProvider):
    """
    AMap REST capability provider exposed through the map provider registry.

    For the official AMap MCP SSE integration, use AMapSSEMCPProvider.
    """

    provider_name = "amap_rest"

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
            return get_weather_forecast(arguments["city"], arguments.get("days", 3))
        raise ValueError(f"Unsupported AMap MCP tool: {tool_name}")
