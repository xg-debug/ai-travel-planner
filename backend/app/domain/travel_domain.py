from __future__ import annotations

import logging
import math
import re
from copy import deepcopy
from typing import Any, Dict, List

from app.mcp_tools import get_mcp_registry
from app.core.config import settings
from app.mcp_tools.amap_provider import AMapMCPError, coordinate
from app.services.runtime_config import get_map_provider
from app.services.cache import get_cache, set_cache, cache_key

logger = logging.getLogger(__name__)


class MapExportValidationError(ValueError):
    pass


def normalize_image_url(value: Any) -> str:
    """Return a browser/mini-program safe external image URL."""
    url = str(value or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("http://"):
        return f"https://{url[7:]}"
    return url if url.startswith("https://") else ""


class TravelDomainService:
    """
    Unified domain layer.

    Workflow and API layers depend on this service instead of relying on
    third-party payloads directly.
    """

    def __init__(self):
        self.registry = get_mcp_registry()

    def search_pois(self, keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        ck = cache_key("mcp_v1", get_map_provider(), city, keyword, str(page), str(size))
        cached = get_cache(ck)
        if cached is not None:
            logger.debug("POI cache hit city=%s keyword=%s", city, keyword)
            return [self._normalize_poi(item, city) for item in cached or [] if isinstance(item, dict)]
        raw_items = self.registry.get("geo").call_tool(
            "geocode_pois",
            {"keyword": keyword, "city": city, "page": page, "size": size},
        )
        result = [self._normalize_poi(item, city) for item in raw_items or []]
        set_cache(ck, result)
        return result

    def get_weather(self, city: str, days: int = 3) -> Dict[str, Any]:
        ck = cache_key("amap_mcp_v1", city, "weather", str(days))
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

    def calculate_route(self, origin: str, destination: str, mode: str = "driving", city: str = "", cityd: str = "") -> Dict[str, Any]:
        origin, destination = coordinate(origin), coordinate(destination)
        ck = cache_key("road_route_v2", get_map_provider(), str(settings.AMAP_ROAD_GEOMETRY_ENABLED), origin, destination, mode, city, cityd)
        cached = get_cache(ck)
        if cached is not None:
            logger.debug("Route cache hit origin=%s destination=%s mode=%s", origin, destination, mode)
            return cached
        road_enabled = settings.AMAP_ROAD_GEOMETRY_ENABLED and get_map_provider() == 'amap_mcp'
        mcp_error = None
        try:
            raw = self.registry.get("geo").call_tool(
                "plan_route",
                {"origin": origin, "destination": destination, "mode": mode, "city": city, "cityd": cityd},
            )
        except AMapMCPError as exc:
            if not road_enabled:
                raise
            mcp_error = exc
            raw = {}
        result = self._normalize_route(raw or {})
        if road_enabled and not result.get('geometry_available'):
            from app.services.amap_road_routes import fetch_road_route
            try:
                # Keep distances, times, instructions and geometry from the same
                # returned route. Planning and both maps share this cache.
                result = self._normalize_route(fetch_road_route(origin, destination, mode, city, cityd))
            except Exception:
                if mcp_error is not None:
                    raise AMapMCPError('高德路线暂时不可用，请稍后重试') from None
                result['geometry_error'] = '道路折线暂未取得，仅保留地点和已有路线指引'
                # A transient geometry failure must not prevent a manual retry.
                return result
        set_cache(ck, result)
        return result

    def search_around(self, location: str, keyword: str = "餐厅", radius: int = 1500, size: int = 6) -> List[Dict[str, Any]]:
        location = coordinate(location)
        ck = cache_key("amap_mcp_v1", "around", location, keyword, str(radius), str(size))
        cached = get_cache(ck)
        if cached is not None:
            return cached
        raw = self.registry.get("amap").call_tool("around_search", {
            "location": location, "keyword": keyword, "radius": radius, "size": size,
        })
        result = [self._normalize_poi(item, "") for item in raw or []]
        set_cache(ck, result)
        return result

    def poi_detail(self, poi_id: str) -> Dict[str, Any]:
        raw = self.registry.get("amap").call_tool("poi_detail", {"id": poi_id})
        return self._normalize_poi(raw, "")

    def export_map(self, title: str, days: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Older saved trips may have coordinates but no POI ID. The official
        # export requires an ID, so only recover an unambiguous nearby match.
        resolved_days = deepcopy(days)
        for day in resolved_days:
            for point in day['pointInfoList']:
                point['poiId'] = str(point.get('poiId') or '').strip()
                if point['poiId']:
                    continue
                name = str(point.get('name') or '').strip()
                normalized_name = re.sub(r'\s+', '', name).replace('（', '(').replace('）', ')')
                candidates = self.search_around(f"{point['lon']},{point['lat']}", name, 500, 10) if name else []
                matches = {}
                for poi in candidates:
                    candidate_name = re.sub(r'\s+', '', poi['name']).replace('（', '(').replace('）', ')')
                    distance = 111320 * math.hypot(
                        poi['lat'] - point['lat'],
                        (poi['lng'] - point['lon']) * math.cos(math.radians(point['lat'])),
                    )
                    if poi.get('verified') and poi.get('id') and candidate_name == normalized_name and distance <= 500:
                        matches[poi['id']] = poi
                if len(matches) != 1:
                    raise MapExportValidationError(f'“{name or "未命名地点"}”缺少高德 POI ID，未能按名称和坐标准确核对；请更新该地点或重新生成行程后导出。')
                point['poiId'] = next(iter(matches))
        return self.registry.get("amap").call_tool("personal_map", {"orgName": title, "lineList": resolved_days})

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
            "image_url": normalize_image_url(item.get("image_url")),
            "source": item.get("source", "geo"),
            "verified": bool(item.get("verified")),
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
            **item,
            "distance": item.get("distance", 0),
            "duration": item.get("duration", 0),
            "steps": item.get("steps", []) or [],
            "toll": item.get("toll", 0),
            "traffic_lights": item.get("traffic_lights", 0),
        }


travel_domain_service = TravelDomainService()
