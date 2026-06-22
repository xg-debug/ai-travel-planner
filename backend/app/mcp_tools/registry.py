from __future__ import annotations

from typing import Dict

from app.mcp_tools.amap_sse_provider import AMapSSEMCPProvider
from app.mcp_tools.amap_provider import AMapMCPProvider
from app.mcp_tools.base import MCPToolProvider
from app.mcp_tools.tencent_provider import TencentMapMCPProvider
from app.services.runtime_config import get_map_provider


class MCPToolRegistry:
    """Registry for capability-specific MCP providers."""

    def __init__(self):
        self._providers: Dict[str, MCPToolProvider] = {}

    def register(self, capability: str, provider: MCPToolProvider) -> None:
        self._providers[capability] = provider

    def get(self, capability: str) -> MCPToolProvider:
        if capability == "geo":
            return self._selected_geo_provider()
        if capability == "weather":
            provider = self._selected_geo_provider()
            if getattr(provider, "provider_name", "") == "tencent":
                return self._providers["geo:amap"]
            return provider

        provider = self._providers.get(capability)
        if not provider:
            available = ", ".join(sorted(self._providers.keys())) or "none"
            raise KeyError(f"MCP capability '{capability}' is not registered. Available: {available}")
        return provider

    def _selected_geo_provider(self) -> MCPToolProvider:
        provider_name = get_map_provider()
        if provider_name == "amap_mcp_sse":
            if "geo:amap_mcp_sse" not in self._providers:
                if not AMapSSEMCPProvider.is_enabled():
                    raise RuntimeError("已选择高德 MCP SSE，但 AMAP_MCP_SSE_URL 未配置")
                self._providers["geo:amap_mcp_sse"] = AMapSSEMCPProvider()
            return self._providers["geo:amap_mcp_sse"]
        if provider_name == "tencent":
            return self._providers.get("geo:tencent", self._providers["geo:amap"])
        return self._providers["geo:amap"]


_registry = MCPToolRegistry()
_registry.register("geo:amap", AMapMCPProvider())
_registry.register("geo:tencent", TencentMapMCPProvider())


def get_mcp_registry() -> MCPToolRegistry:
    return _registry
