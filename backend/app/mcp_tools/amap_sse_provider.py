"""Compatibility import: legacy SSE configurations now use official HTTP MCP."""
from app.mcp_tools.amap_provider import AMapMCPProvider

AMapSSEMCPProvider = AMapMCPProvider
