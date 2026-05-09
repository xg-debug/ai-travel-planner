from __future__ import annotations

from typing import Dict

from app.mcp_tools.agentichotel_provider import AgenticHotelMCPProvider
from app.mcp_tools.amap_provider import AMapMCPProvider
from app.mcp_tools.base import MCPToolProvider


class MCPToolRegistry:
    """Registry for capability-specific MCP providers."""

    def __init__(self):
        self._providers: Dict[str, MCPToolProvider] = {}

    def register(self, capability: str, provider: MCPToolProvider) -> None:
        self._providers[capability] = provider

    def get(self, capability: str) -> MCPToolProvider:
        provider = self._providers.get(capability)
        if not provider:
            available = ", ".join(sorted(self._providers.keys())) or "none"
            raise KeyError(f"MCP capability '{capability}' is not registered. Available: {available}")
        return provider


_registry = MCPToolRegistry()
_geo_provider = AMapMCPProvider()
_registry.register("geo", _geo_provider)
_registry.register("hotel", AgenticHotelMCPProvider() if AgenticHotelMCPProvider.is_enabled() else _geo_provider)
_registry.register("weather", _registry.get("geo"))


def get_mcp_registry() -> MCPToolRegistry:
    return _registry
