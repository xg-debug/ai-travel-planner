from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.mcp_tools import get_mcp_registry

logger = logging.getLogger(__name__)


class TravelDomainService:
    """
    Unified domain layer.

    Agent and API layers depend on this service instead of relying on
    third-party payloads directly.
    """

    def __init__(self):
        self.registry = get_mcp_registry()

    def search_pois(self, keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        raw_items = self.registry.get("geo").call_tool(
            "geocode_pois",
            {"keyword": keyword, "city": city, "page": page, "size": size},
        )
        return [self._normalize_poi(item, city) for item in raw_items or []]

    def search_hotels(self, keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        args = {"keyword": keyword, "city": city, "page": page, "size": size}
        hotel_provider = self.registry.get("hotel")
        geo_provider = self.registry.get("geo")

        raw_items: List[Dict[str, Any]] = []
        try:
            raw_items = hotel_provider.call_tool("search_hotels", args) or []
        except Exception as exc:
            provider_name = getattr(hotel_provider, "provider_name", "hotel")
            logger.warning(
                "Hotel provider failed provider=%s city=%s keyword=%s error=%s",
                provider_name,
                city,
                keyword,
                exc,
            )

        if raw_items:
            return [self._normalize_hotel(item, city) for item in raw_items]

        if hotel_provider is geo_provider:
            return []

        logger.info(
            "Hotel provider returned no usable results, fallback to geo provider city=%s keyword=%s",
            city,
            keyword,
        )
        fallback_items = geo_provider.call_tool("search_hotels", args) or []
        return [self._normalize_hotel(item, city) for item in fallback_items]

    def get_weather(self, city: str, days: int = 3) -> Dict[str, Any]:
        raw = self.registry.get("weather").call_tool(
            "get_weather_forecast",
            {"city": city, "days": days},
        )
        return self._normalize_weather(raw or {}, city)

    def calculate_route(self, origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
        raw = self.registry.get("geo").call_tool(
            "plan_route",
            {"origin": origin, "destination": destination, "mode": mode},
        )
        return self._normalize_route(raw or {})

    def _normalize_poi(self, item: Dict[str, Any], city: str) -> Dict[str, Any]:
        return {
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "lat": float(item.get("lat", 0) or 0),
            "lng": float(item.get("lng", 0) or 0),
            "address": item.get("address", ""),
            "type": item.get("type", ""),
            "rating": float(item.get("rating", 0) or 0),
            "price": item.get("price", ""),
            "description": item.get("description", ""),
            "opening_hours": item.get("opening_hours", ""),
            "best_time": item.get("best_time", ""),
            "tips": item.get("tips", ""),
            "image_url": item.get("image_url"),
            "source": item.get("source", "geo"),
        }

    def _normalize_hotel(self, item: Dict[str, Any], city: str) -> Dict[str, Any]:
        poi = self._normalize_poi(item, city)
        poi["type"] = "酒店"
        poi["opening_hours"] = item.get("opening_hours", "")
        poi["source"] = item.get("source", "hotel")
        return poi

    def _normalize_weather(self, item: Dict[str, Any], city: str) -> Dict[str, Any]:
        forecast_items = []
        for forecast in item.get("forecast", []) or []:
            forecast_items.append(
                {
                    "date": forecast.get("date", ""),
                    "condition": forecast.get("condition", ""),
                    "day_condition": forecast.get("day_condition") or forecast.get("condition", ""),
                    "night_condition": forecast.get("night_condition") or forecast.get("condition", ""),
                    "temperature": forecast.get("temperature", {"min": 0, "max": 0, "avg": 0}),
                    "humidity": forecast.get("humidity", 0),
                    "wind_speed": forecast.get("wind_speed", 0),
                    "day_wind_direction": forecast.get("day_wind_direction", ""),
                    "night_wind_direction": forecast.get("night_wind_direction", ""),
                    "day_wind_power": forecast.get("day_wind_power", ""),
                    "night_wind_power": forecast.get("night_wind_power", ""),
                    "icon": forecast.get("icon", "unknown"),
                }
            )
        return {
            "city": item.get("city", city),
            "report_time": item.get("report_time", ""),
            "forecast": forecast_items,
        }

    def _normalize_route(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "distance": item.get("distance", 0),
            "duration": item.get("duration", 0),
            "steps": item.get("steps", []) or [],
            "toll": item.get("toll", 0),
            "traffic_lights": item.get("traffic_lights", 0),
        }


travel_domain_service = TravelDomainService()
