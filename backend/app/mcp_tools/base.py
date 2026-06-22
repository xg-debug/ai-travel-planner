from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict

from app.mcp_tools.client import MCPServerConfig, call_mcp_tool


class MCPToolProvider(ABC):
    """Base abstraction for one external capability provider."""

    provider_name = "base"

    @abstractmethod
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        raise NotImplementedError


def run_async_sync(coro):
    """Run async MCP calls from sync code, even if an event loop already exists."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


class StdioMCPToolProvider(MCPToolProvider):
    """Generic stdio-based MCP provider backed by the local MCP client."""

    provider_name = "stdio_mcp"

    def __init__(self, config: MCPServerConfig):
        self.config = config

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        result = run_async_sync(call_mcp_tool(self.config, tool_name, arguments))
        if isinstance(result, dict) and "content" in result and len(result) == 1:
            return result["content"]
        return result
