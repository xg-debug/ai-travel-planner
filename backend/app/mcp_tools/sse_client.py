from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urljoin, urlparse

import aiohttp

from app.mcp_tools.client import (
    DEFAULT_MCP_PROTOCOL_VERSION,
    JSONRPC_VERSION,
    MCPError,
    MCPProtocolError,
    MCPToolError,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MCPSSEServerConfig:
    """Configuration for a remote MCP server using the SSE transport."""

    sse_url: str
    message_url: Optional[str] = None
    headers: Dict[str, str] | None = None
    connect_timeout: float = 20.0
    request_timeout: float = 60.0
    protocol_version: str = DEFAULT_MCP_PROTOCOL_VERSION
    client_name: str = "ai-travel-planner"
    client_version: str = "1.0.0"


class SSEMCPClient:
    """
    Minimal MCP client for remote SSE servers.

    MCP over SSE opens a long-lived GET stream first. The server then sends an
    `endpoint` event telling the client where JSON-RPC messages should be POSTed.
    Responses are delivered back through the SSE stream as `message` events.
    """

    def __init__(self, config: MCPSSEServerConfig):
        if not config.sse_url:
            raise ValueError("sse_url is required")
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._sse_response: aiohttp.ClientResponse | None = None
        self._reader_task: asyncio.Task | None = None
        self._pending: Dict[int, asyncio.Future] = {}
        self._request_id = 0
        self._message_url: str | None = config.message_url
        self._initialized = False
        self._server_info: Dict[str, Any] = {}
        self._capabilities: Dict[str, Any] = {}
        self._message_endpoint_ready = asyncio.Event()

    async def __aenter__(self) -> "SSEMCPClient":
        await self.connect()
        return self

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        await self.close()

    @property
    def is_connected(self) -> bool:
        return self._session is not None and not self._session.closed and self._reader_task is not None

    async def connect(self) -> None:
        if self.is_connected:
            return

        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=self.config.connect_timeout,
            sock_connect=self.config.connect_timeout,
            sock_read=None,
        )
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            **(self.config.headers or {}),
        }
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        try:
            logger.info("Connecting MCP SSE server: %s", self.config.sse_url)
            self._sse_response = await self._session.get(self.config.sse_url)
            self._sse_response.raise_for_status()
            self._reader_task = asyncio.create_task(self._read_sse_stream())

            if not self._message_url:
                await asyncio.wait_for(self._message_endpoint_ready.wait(), timeout=self.config.connect_timeout)

            await asyncio.wait_for(self.initialize(), timeout=self.config.request_timeout)
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(MCPError("MCP SSE client closed"))
        self._pending.clear()

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._sse_response:
            self._sse_response.close()
            self._sse_response = None

        if self._session:
            await self._session.close()
            self._session = None

        self._initialized = False
        self._message_endpoint_ready = asyncio.Event()

    async def initialize(self) -> Dict[str, Any]:
        response = await self._request(
            "initialize",
            {
                "protocolVersion": self.config.protocol_version,
                "capabilities": {},
                "clientInfo": {
                    "name": self.config.client_name,
                    "version": self.config.client_version,
                },
            },
        )
        self._server_info = response.get("serverInfo") or {}
        self._capabilities = response.get("capabilities") or {}
        self._initialized = True
        await self._notify("notifications/initialized", {})
        return response

    async def list_tools(self) -> list[Dict[str, Any]]:
        self._ensure_ready()
        result = await self._request("tools/list", {})
        tools = result.get("tools") or []
        if not isinstance(tools, list):
            raise MCPProtocolError("tools/list returned a non-list 'tools' payload")
        return tools

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._ensure_ready()
        result = await self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )
        if result.get("isError"):
            raise MCPToolError(f"MCP tool '{name}' returned an error: {result}")
        return result

    async def ensure_tool_exists(self, name: str) -> Dict[str, Any]:
        tools = await self.list_tools()
        tool_map = {str(tool.get("name")): tool for tool in tools if tool.get("name")}
        tool = tool_map.get(name)
        if not tool:
            available = ", ".join(sorted(tool_map.keys())) or "none"
            raise MCPToolError(f"Tool '{name}' not found. Available tools: {available}")
        return tool

    async def _notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        payload: Dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": method}
        if params is not None:
            payload["params"] = params
        await self._post_jsonrpc(payload)

    async def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._ensure_connected()
        self._request_id += 1
        request_id = self._request_id
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[request_id] = future

        payload: Dict[str, Any] = {
            "jsonrpc": JSONRPC_VERSION,
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        try:
            await self._post_jsonrpc(payload)
            response = await asyncio.wait_for(future, timeout=self.config.request_timeout)
        finally:
            self._pending.pop(request_id, None)

        if "error" in response:
            error = response["error"] or {}
            raise MCPToolError(f"MCP request '{method}' failed: {error.get('message') or error}")

        result = response.get("result")
        if result is None:
            return {}
        if not isinstance(result, dict):
            raise MCPProtocolError(f"MCP request '{method}' returned non-object result: {result!r}")
        return result

    async def _post_jsonrpc(self, payload: Dict[str, Any]) -> None:
        self._ensure_connected()
        if not self._message_url:
            await asyncio.wait_for(self._message_endpoint_ready.wait(), timeout=self.config.connect_timeout)
        if not self._message_url:
            raise MCPProtocolError("MCP SSE message endpoint was not provided by the server")

        assert self._session is not None
        async with self._session.post(self._message_url, json=payload) as response:
            if response.status >= 400:
                text = await response.text()
                raise MCPProtocolError(f"MCP SSE POST failed status={response.status} body={text[:300]}")

    async def _read_sse_stream(self) -> None:
        assert self._sse_response is not None
        event_name = "message"
        data_lines: list[str] = []

        async for raw_line in self._sse_response.content:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                await self._dispatch_event(event_name, "\n".join(data_lines))
                event_name = "message"
                data_lines = []
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line[6:].strip() or "message"
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())

    async def _dispatch_event(self, event_name: str, data: str) -> None:
        if not data:
            return

        if event_name == "endpoint":
            self._message_url = self._resolve_message_url(data)
            self._message_endpoint_ready.set()
            return

        if event_name not in {"message", "response"}:
            logger.debug("Ignored MCP SSE event event=%s data=%s", event_name, data[:300])
            return

        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            logger.debug("Ignored non-JSON MCP SSE message: %s", data[:300])
            return
        if not isinstance(payload, dict):
            return

        response_id = payload.get("id")
        if response_id is None:
            logger.debug("Ignored MCP SSE notification: %s", payload)
            return

        future = self._pending.get(int(response_id))
        if future and not future.done():
            future.set_result(payload)

    def _resolve_message_url(self, endpoint: str) -> str:
        endpoint = endpoint.strip()
        if not endpoint:
            raise MCPProtocolError("MCP SSE endpoint event was empty")
        parsed = urlparse(endpoint)
        if parsed.scheme and parsed.netloc:
            return endpoint
        return urljoin(self.config.sse_url, endpoint)

    def _ensure_connected(self) -> None:
        if not self._session or self._session.closed:
            raise MCPError("MCP SSE client is not connected")

    def _ensure_ready(self) -> None:
        self._ensure_connected()
        if not self._initialized:
            raise MCPError("MCP SSE client is not initialized")


async def call_mcp_sse_tool(
    config: MCPSSEServerConfig,
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    async with SSEMCPClient(config) as client:
        await client.ensure_tool_exists(tool_name)
        return await client.call_tool(tool_name, arguments or {})
