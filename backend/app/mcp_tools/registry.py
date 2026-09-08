from __future__ import annotations
from app.mcp_tools.amap_provider import AMapMCPProvider
from app.mcp_tools.base import MCPToolProvider
from app.mcp_tools.tencent_provider import TencentMapMCPProvider
from app.services.runtime_config import get_map_provider


class MCPToolRegistry:
    def __init__(self):
        self._providers = {'geo:amap_mcp': AMapMCPProvider(), 'geo:tencent': TencentMapMCPProvider()}

    def register(self, capability: str, provider: MCPToolProvider) -> None:
        self._providers[capability] = provider

    def get(self, capability: str) -> MCPToolProvider:
        if capability in {'weather', 'amap'}:
            return self._providers['geo:amap_mcp']
        if capability == 'geo':
            return self._providers['geo:tencent' if get_map_provider() == 'tencent' else 'geo:amap_mcp']
        return self._providers[capability]


_registry = MCPToolRegistry()

def get_mcp_registry() -> MCPToolRegistry:
    return _registry
