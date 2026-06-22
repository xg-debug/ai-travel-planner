from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.mcp_tools import get_mcp_registry
from app.services.cache import get_cache, set_cache, cache_key

logger = logging.getLogger(__name__)


class TravelDomainService:
    """
    Unified domain layer.

    Workflow and API layers depend on this service instead of relying on
    third-party payloads directly.
    """

    def __init__(self):
        self.registry = get_mcp_registry()

    def search_pois(self, keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        ck = cache_key(city, keyword, str(page), str(size))
        cached = get_cache(ck)
        if cached is not None:
            logger.debug("POI cache hit city=%s keyword=%s", city, keyword)
            return cached
        raw_items = self.registry.get("geo").call_tool(
            "geocode_pois",
            {"keyword": keyword, "city": city, "page": page, "size": size},
        )
        result = [self._normalize_poi(item, city) for item in raw_items or []]
        set_cache(ck, result)
        return result

    def get_weather(self, city: str, days: int = 3) -> Dict[str, Any]:
        ck = cache_key(city, "weather", str(days))
        cached = get_cache(ck)
        if cached is not None:
            logger.debug("Weather cache hit city=%s days=%s", city, days)
            return cached
        raw = self.registry.get("weather").call_tool(
            "get_weather_forecast",
            {"city": city, "days": days},
        )
        result = self._normalize_weather(raw or {}, city)
        set_cache(ck, result)
        return result

    def calculate_route(self, origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
        ck = cache_key("route", origin, destination, mode)
        cached = get_cache(ck)
        if cached is not None:
            logger.debug("Route cache hit origin=%s destination=%s mode=%s", origin, destination, mode)
            return cached
        raw = self.registry.get("geo").call_tool(
            "plan_route",
            {"origin": origin, "destination": destination, "mode": mode},
        )
        result = self._normalize_route(raw or {})
        set_cache(ck, result)
        return result

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
            "avg_cost": int(float(item.get("avg_cost", 0) or 0)),
            "price_source": item.get("price_source", ""),
            "price_confidence": item.get("price_confidence", ""),
            "price_unit": item.get("price_unit", ""),
            "price_note": item.get("price_note", ""),
            "description": item.get("description", ""),
            "opening_hours": item.get("opening_hours", ""),
            "best_time": item.get("best_time", ""),
            "tips": item.get("tips", ""),
            "image_url": item.get("image_url"),
            "source": item.get("source", "geo"),
        }

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
