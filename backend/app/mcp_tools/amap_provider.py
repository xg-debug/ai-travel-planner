from __future__ import annotations

from typing import Any, Dict

from app.mcp_tools.base import MCPToolProvider
from app.services.amap_service import calculate_route, get_weather_forecast, search_hotels, search_pois


class AMapMCPProvider(MCPToolProvider):
    """
    AMap capability provider exposed through the MCP tool layer.

    This keeps current HTTP-based AMap integration usable while letting
    upper layers depend on a provider abstraction instead of directly
    importing service modules.
    """

    provider_name = "amap"

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if tool_name == "geocode_pois":
            return search_pois(
                arguments["keyword"],
                arguments["city"],
                arguments.get("page", 1),
                arguments.get("size", 10),
            )
        if tool_name == "search_hotels":
            return search_hotels(
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
