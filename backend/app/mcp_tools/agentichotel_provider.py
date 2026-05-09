from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List

from app.core.config import settings
from app.mcp_tools.base import StdioMCPToolProvider
from app.services.mcp_client import MCPServerConfig


logger = logging.getLogger(__name__)


class AgenticHotelMCPProvider(StdioMCPToolProvider):
    """Hotel capability provider backed by AgenticHotel / RollingGo MCP."""

    provider_name = "agentichotel"

    def __init__(self):
        env: Dict[str, str] = {}
        if settings.ROLLINGGO_API_KEY:
            env["ROLLINGGO_API_KEY"] = settings.ROLLINGGO_API_KEY
        if settings.AIGOHOTEL_API_KEY:
            env["AIGOHOTEL_API_KEY"] = settings.AIGOHOTEL_API_KEY

        args = [item for item in settings.AGENTICHOTEL_MCP_ARGS.split() if item]
        super().__init__(
            MCPServerConfig(
                command=settings.AGENTICHOTEL_MCP_COMMAND,
                args=args,
                cwd=settings.AGENTICHOTEL_MCP_CWD,
                env=env,
                startup_timeout=settings.AGENTICHOTEL_MCP_STARTUP_TIMEOUT,
                request_timeout=settings.AGENTICHOTEL_MCP_REQUEST_TIMEOUT,
            )
        )

    @staticmethod
    def is_enabled() -> bool:
        provider = (settings.HOTEL_PROVIDER or "auto").lower()
        if provider not in {"auto", "agentichotel"}:
            return False
        return bool(
            AgenticHotelMCPProvider._is_real_key(settings.ROLLINGGO_API_KEY)
            or AgenticHotelMCPProvider._is_real_key(settings.AIGOHOTEL_API_KEY)
        )

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if tool_name == "search_hotels":
            return self._search_hotels(arguments)
        if tool_name == "get_hotel_detail":
            hotel_id = str(arguments.get("hotel_id") or arguments.get("id") or "").strip()
            if not hotel_id:
                raise ValueError("hotel_id is required")
            return self._normalize_payload(super().call_tool("getHotelDetail", {"hotelId": hotel_id}))
        if tool_name == "get_hotel_search_tags":
            city = str(arguments.get("city") or "").strip()
            keyword = str(arguments.get("keyword") or "").strip()
            params = {"place": city, "originalQuery": keyword or city}
            return self._normalize_payload(super().call_tool("getHotelSearchTags", params))
        raise ValueError(f"Unsupported AgenticHotel MCP tool: {tool_name}")

    def _search_hotels(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        keyword = str(arguments.get("keyword") or "").strip()
        city = str(arguments.get("city") or "").strip()
        size = int(arguments.get("size") or 8)
        candidate_payloads: List[Dict[str, Any]] = [
            {
                "originalQuery": f"{city} {keyword}".strip(),
                "place": city,
                "limit": size,
                "language": "zh-CN",
            },
            {
                "query": keyword,
                "city": city,
                "size": size,
            },
            {
                "keyword": keyword,
                "city": city,
                "size": size,
            },
        ]

        last_error: Exception | None = None
        for payload in candidate_payloads:
            try:
                raw = super().call_tool("searchHotels", payload)
                normalized = self._normalize_payload(raw)
                hotels = self._extract_hotel_items(normalized)
                if hotels:
                    return hotels[:size]
            except Exception as exc:
                last_error = exc
                logger.info("AgenticHotel searchHotels payload failed payload=%s error=%s", payload, exc)

        if last_error:
            raise last_error
        return []

    def _normalize_payload(self, payload: Any) -> Any:
        if isinstance(payload, list):
            blocks = list(payload)
            if len(blocks) == 1 and isinstance(blocks[0], dict):
                block = blocks[0]
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    text = block["text"].strip()
                    if text:
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            return {"text": text}
            return [self._normalize_payload(item) for item in blocks]
        return payload

    def _extract_hotel_items(self, payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, list):
            return [self._normalize_hotel_item(item) for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("hotels", "items", "results", "data", "list"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [self._normalize_hotel_item(item) for item in value if isinstance(item, dict)]
            if any(key in payload for key in ("hotelId", "id", "name", "hotelName")):
                return [self._normalize_hotel_item(payload)]
        return []

    def _normalize_hotel_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        latitude = self._pick_first(item, ("lat", "latitude", "geoLat", "y"))
        longitude = self._pick_first(item, ("lng", "lon", "longitude", "geoLng", "x"))
        address = self._pick_first(item, ("address", "fullAddress", "addr")) or ""
        rating = self._pick_first(item, ("rating", "score", "starRating", "reviewScore")) or 0
        price = (
            self._pick_first(item, ("priceText", "priceDisplay", "startingPrice", "minPrice", "price"))
            or ""
        )
        name = self._pick_first(item, ("name", "hotelName", "title")) or ""
        hotel_id = self._pick_first(item, ("id", "hotelId", "hid")) or name
        description = self._pick_first(item, ("description", "summary", "intro")) or ""
        return {
            "id": str(hotel_id),
            "name": str(name),
            "lat": self._safe_float(latitude),
            "lng": self._safe_float(longitude),
            "address": str(address),
            "type": "酒店",
            "rating": self._safe_float(rating, 0.0),
            "price": price,
            "description": description,
            "opening_hours": "",
            "best_time": "",
            "tips": str(self._pick_first(item, ("tags", "highlights")) or ""),
            "image_url": self._pick_first(item, ("image", "imageUrl", "cover", "thumbnail")),
            "source": "agentichotel",
            "raw": item,
        }

    @staticmethod
    def _pick_first(item: Dict[str, Any], keys: Iterable[str]) -> Any:
        for key in keys:
            value = item.get(key)
            if value not in (None, "", []):
                return value
        return None

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _is_real_key(value: Any) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        placeholder_markers = ("replace_with_", "your_", "test_", "demo_")
        return not any(text.lower().startswith(marker) for marker in placeholder_markers)
