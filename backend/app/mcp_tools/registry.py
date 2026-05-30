from __future__ import annotations

from typing import Dict

from app.mcp_tools.agentichotel_provider import AgenticHotelMCPProvider
from app.mcp_tools.amap_provider import AMapMCPProvider
from app.mcp_tools.base import MCPToolProvider
from app.mcp_tools.tencent_provider import TencentMapMCPProvider
from app.services.runtime_config import get_map_provider


class MCPToolRegistry:
    """Registry for capability-specific MCP providers."""

    def __init__(self):
        self._providers: Dict[str, MCPToolProvider] = {}
        self._agentic_hotel_provider: MCPToolProvider | None = None

    def register(self, capability: str, provider: MCPToolProvider) -> None:
        self._providers[capability] = provider

    def register_agentic_hotel(self, provider: MCPToolProvider) -> None:
        self._agentic_hotel_provider = provider

    def get(self, capability: str) -> MCPToolProvider:
        if capability == "geo":
            return self._selected_geo_provider()
        if capability == "hotel":
            return self._agentic_hotel_provider or self._selected_geo_provider()
        if capability == "weather":
            return self._providers["geo:amap"]

        provider = self._providers.get(capability)
        if not provider:
            available = ", ".join(sorted(self._providers.keys())) or "none"
            raise KeyError(f"MCP capability '{capability}' is not registered. Available: {available}")
        return provider

    def _selected_geo_provider(self) -> MCPToolProvider:
        provider_name = get_map_provider()
        if provider_name == "tencent":
            return self._providers["geo:tencent"]
        return self._providers["geo:amap"]


_registry = MCPToolRegistry()
_geo_provider = AMapMCPProvider()
_registry.register("geo:amap", _geo_provider)
_registry.register("geo:tencent", TencentMapMCPProvider())
if AgenticHotelMCPProvider.is_enabled():
    _registry.register_agentic_hotel(AgenticHotelMCPProvider())


def get_mcp_registry() -> MCPToolRegistry:
    return _registry
