import asyncio
import contextlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional


logger = logging.getLogger(__name__)

JSONRPC_VERSION = "2.0"
DEFAULT_MCP_PROTOCOL_VERSION = "2024-11-05"


class MCPError(RuntimeError):
    """Base exception for MCP client failures."""


class MCPProtocolError(MCPError):
    """Raised when the MCP server returns malformed protocol data."""


class MCPToolError(MCPError):
    """Raised when an MCP tool call returns an error response."""


@dataclass(slots=True)
class MCPServerConfig:
    """Configuration for spawning an MCP server over stdio."""

    command: str
    args: list[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    startup_timeout: float = 20.0
    request_timeout: float = 60.0
    protocol_version: str = DEFAULT_MCP_PROTOCOL_VERSION
    client_name: str = "ai-travel-planner"
    client_version: str = "1.0.0"

    @classmethod
    def from_env(
        cls,
        *,
        command_env: str,
        args_env: Optional[str] = None,
        cwd_env: Optional[str] = None,
        startup_timeout_env: Optional[str] = None,
        request_timeout_env: Optional[str] = None,
        extra_env_keys: Optional[Iterable[str]] = None,
        default_args: Optional[list[str]] = None,
    ) -> "MCPServerConfig":
        command = str(os.getenv(command_env, "")).strip()
        if not command:
            raise ValueError(f"Environment variable {command_env} is required")

        raw_args = str(os.getenv(args_env or "", "")).strip() if args_env else ""
        args = raw_args.split() if raw_args else list(default_args or [])
        cwd = str(os.getenv(cwd_env, "")).strip() or None if cwd_env else None

        extra_env: Dict[str, str] = {}
        for key in extra_env_keys or []:
            value = os.getenv(key)
            if value:
                extra_env[key] = value

        startup_timeout = float(os.getenv(startup_timeout_env, "20")) if startup_timeout_env else 20.0
        request_timeout = float(os.getenv(request_timeout_env, "60")) if request_timeout_env else 60.0

        return cls(
            command=command,
            args=args,
            cwd=cwd,
            env=extra_env,
            startup_timeout=startup_timeout,
            request_timeout=request_timeout,
        )


class MCPClient:
    """
    Minimal MCP stdio client without third-party dependencies.

    It speaks JSON-RPC over stdio using the MCP wire format with
    `Content-Length` headers, and supports:
    - initialize
    - ping
    - tools/list
    - tools/call
    """

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._process: Optional[asyncio.subprocess.Process] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._request_lock = asyncio.Lock()
        self._request_id = 0
        self._server_info: Dict[str, Any] = {}
        self._capabilities: Dict[str, Any] = {}
        self._initialized = False

    @property
    def is_connected(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def server_info(self) -> Dict[str, Any]:
        return dict(self._server_info)

    @property
    def server_capabilities(self) -> Dict[str, Any]:
        return dict(self._capabilities)

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        await self.close()

    async def connect(self) -> None:
        if self.is_connected:
            return

        logger.info("Starting MCP server: %s %s", self.config.command, " ".join(self.config.args))
        process = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.config.cwd,
            env={**os.environ, **self.config.env},
        )

        if not process.stdin or not process.stdout:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            raise MCPError("Failed to open stdio pipes for MCP server")

        self._process = process
        self._reader = process.stdout
        self._writer = process.stdin
        self._stderr_task = asyncio.create_task(self._drain_stderr(process))

        try:
            await asyncio.wait_for(self.initialize(), timeout=self.config.startup_timeout)
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        writer = self._writer
        process = self._process

        self._initialized = False
        self._reader = None
        self._writer = None
        self._process = None
        self._server_info = {}
        self._capabilities = {}

        if writer:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()

        if process and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=3)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                await process.wait()

        if self._stderr_task:
            self._stderr_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stderr_task
            self._stderr_task = None

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

    async def ping(self) -> Dict[str, Any]:
        self._ensure_ready()
        return await self._request("ping", {})

    async def list_tools(self) -> list[Dict[str, Any]]:
        self._ensure_ready()
        result = await self._request("tools/list", {})
        tools = result.get("tools") or []
        if not isinstance(tools, list):
            raise MCPProtocolError("tools/list returned a non-list 'tools' payload")
        return tools

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._ensure_ready()
        if not name:
            raise ValueError("Tool name is required")

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

    async def get_tool_map(self) -> Dict[str, Dict[str, Any]]:
        tools = await self.list_tools()
        return {str(tool.get("name")): tool for tool in tools if tool.get("name")}

    async def ensure_tool_exists(self, name: str) -> Dict[str, Any]:
        tool_map = await self.get_tool_map()
        tool = tool_map.get(name)
        if not tool:
            available = ", ".join(sorted(tool_map.keys())) or "none"
            raise MCPToolError(f"Tool '{name}' not found. Available tools: {available}")
        return tool

    async def _notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        message = {
            "jsonrpc": JSONRPC_VERSION,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        await self._write_message(message)

    async def _request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with self._request_lock:
            self._ensure_connected()
            self._request_id += 1
            request_id = self._request_id
            payload = {
                "jsonrpc": JSONRPC_VERSION,
                "id": request_id,
                "method": method,
            }
            if params is not None:
                payload["params"] = params

            await self._write_message(payload)

            while True:
                response = await asyncio.wait_for(self._read_message(), timeout=self.config.request_timeout)

                # Ignore notifications and keep waiting for the matching response.
                if "id" not in response:
                    logger.debug("Ignored MCP notification: %s", response)
                    continue

                if response["id"] != request_id:
                    raise MCPProtocolError(
                        f"Received mismatched MCP response id={response['id']} expected={request_id}"
                    )

                if "error" in response:
                    error = response["error"] or {}
                    raise MCPToolError(
                        f"MCP request '{method}' failed: {error.get('message') or error}"
                    )

                result = response.get("result")
                if not isinstance(result, dict):
                    if result is None:
                        return {}
                    raise MCPProtocolError(f"MCP request '{method}' returned non-object result: {result!r}")
                return result

    async def _write_message(self, payload: Dict[str, Any]) -> None:
        self._ensure_connected()
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        assert self._writer is not None
        self._writer.write(header + body)
        await self._writer.drain()

    async def _read_message(self) -> Dict[str, Any]:
        self._ensure_connected()
        assert self._reader is not None

        headers: Dict[str, str] = {}
        while True:
            raw_line = await self._reader.readline()
            if not raw_line:
                raise MCPProtocolError("MCP server closed stdout unexpectedly")
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                break
            if ":" not in line:
                raise MCPProtocolError(f"Malformed MCP header line: {line!r}")
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

        content_length = headers.get("content-length")
        if not content_length:
            raise MCPProtocolError("Missing Content-Length header in MCP response")

        try:
            body_size = int(content_length)
        except ValueError as exc:
            raise MCPProtocolError(f"Invalid Content-Length header: {content_length!r}") from exc

        raw_body = await self._reader.readexactly(body_size)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MCPProtocolError(f"Failed to decode MCP JSON body: {exc}") from exc

        if not isinstance(payload, dict):
            raise MCPProtocolError(f"MCP response is not a JSON object: {payload!r}")
        return payload

    async def _drain_stderr(self, process: asyncio.subprocess.Process) -> None:
        if not process.stderr:
            return
        while True:
            line = await process.stderr.readline()
            if not line:
                return
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                logger.info("MCP stderr[%s]: %s", self.config.command, text)

    def _ensure_connected(self) -> None:
        if not self.is_connected or not self._reader or not self._writer:
            raise MCPError("MCP client is not connected")

    def _ensure_ready(self) -> None:
        self._ensure_connected()
        if not self._initialized:
            raise MCPError("MCP client is not initialized")


async def call_mcp_tool(
    config: MCPServerConfig,
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """One-shot helper for simple tool invocations."""
    async with MCPClient(config) as client:
        await client.ensure_tool_exists(tool_name)
        return await client.call_tool(tool_name, arguments or {})
