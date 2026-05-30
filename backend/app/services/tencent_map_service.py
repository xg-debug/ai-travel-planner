import logging
from typing import Any, Dict, List

import requests

from app.services.runtime_config import get_map_api_key

logger = logging.getLogger(__name__)


class TencentMapService:
    """腾讯位置服务：路线规划。"""

    def __init__(self) -> None:
        self.base_url = "https://apis.map.qq.com/ws/direction/v1"
        self.place_url = "https://apis.map.qq.com/ws/place/v1/search"
        self.mode_paths = {
            "driving": "driving",
            "walking": "walking",
            "bicycling": "bicycling",
            "transit": "transit",
        }

    @property
    def api_key(self) -> str | None:
        return get_map_api_key("tencent")

    def search_pois(self, keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("TENCENT_MAP_API_KEY 未配置，无法使用腾讯位置服务搜索 POI")

        params = {
            "key": self.api_key,
            "keyword": keyword,
            "boundary": f"region({city},0)",
            "page_size": size,
            "page_index": page,
            "output": "json",
        }

        try:
            response = requests.get(self.place_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != 0:
                raise RuntimeError(str(data.get("message") or "腾讯位置服务搜索失败"))

            results = []
            for item in data.get("data", []) or []:
                location = item.get("location") or {}
                results.append(
                    {
                        "id": str(item.get("id") or item.get("_distance") or item.get("title") or ""),
                        "name": item.get("title") or "",
                        "lat": float(location.get("lat") or 0),
                        "lng": float(location.get("lng") or 0),
                        "address": item.get("address") or city,
                        "type": item.get("category") or "",
                        "rating": 0.0,
                        "price": "",
                        "description": f"{item.get('title') or ''}位于{item.get('address') or city}",
                        "opening_hours": "",
                        "best_time": "",
                        "tips": "",
                        "image_url": None,
                        "source": "tencent",
                    }
                )
            return results
        except Exception as exc:
            logger.error("Error searching Tencent POIs: %s", exc)
            raise

    def search_hotels(self, keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        queries = [keyword, f"{city}酒店", f"{city}宾馆"]
        results: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for query in queries:
            for item in self.search_pois(query, city, page, size):
                name = str(item.get("name") or "").strip()
                if not name or name in seen:
                    continue
                item["type"] = "酒店"
                seen.add(name)
                results.append(item)
                if len(results) >= size:
                    return results
        return results

    def plan_day_route(self, points: List[Dict[str, Any]], mode: str = "driving") -> Dict[str, Any]:
        if len(points) < 2:
            return {"distance": 0, "duration": 0, "polyline": [], "legs": []}

        legs = []
        merged_polyline: List[Dict[str, float]] = []
        total_distance = 0
        total_duration = 0

        for index in range(len(points) - 1):
            leg = self.plan_segment(points[index], points[index + 1], mode)
            leg["fromIndex"] = index
            leg["toIndex"] = index + 1
            legs.append(leg)

            total_distance += int(leg.get("distance") or 0)
            total_duration += int(leg.get("duration") or 0)

            leg_polyline = leg.get("polyline") or []
            if not leg_polyline:
                continue
            if merged_polyline:
                merged_polyline.extend(leg_polyline[1:])
            else:
                merged_polyline.extend(leg_polyline)

        return {
            "distance": total_distance,
            "duration": total_duration,
            "polyline": merged_polyline,
            "legs": legs,
        }

    def plan_segment(self, origin: Dict[str, Any], destination: Dict[str, Any], mode: str = "driving") -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("TENCENT_MAP_API_KEY 未配置，无法使用腾讯地图路线规划")

        mode_path = self.mode_paths.get(mode, "driving")
        origin_text = self._format_coordinate(origin)
        destination_text = self._format_coordinate(destination)

        params = {
            "key": self.api_key,
            "from": origin_text,
            "to": destination_text,
            "output": "json",
        }

        try:
            response = requests.get(f"{self.base_url}/{mode_path}/", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != 0:
                message = data.get("message") or data.get("detail") or "腾讯地图路线规划失败"
                raise RuntimeError(str(message))

            routes = ((data.get("result") or {}).get("routes") or [])
            if not routes:
                raise RuntimeError("腾讯地图未返回可用路线")

            route = routes[0]
            polyline = self._decode_polyline(route.get("polyline"))
            duration_minutes = int(route.get("duration") or 0)
            return {
                "distance": int(route.get("distance") or 0),
                "duration": duration_minutes * 60,
                "polyline": polyline,
            }
        except Exception as exc:
            logger.error("Error planning Tencent route: %s", exc)
            raise

    def calculate_route(self, origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
        origin_point = self._parse_lng_lat_text(origin)
        destination_point = self._parse_lng_lat_text(destination)
        route = self.plan_segment(origin_point, destination_point, mode)
        return {
            "distance": route.get("distance", 0),
            "duration": route.get("duration", 0),
            "steps": [],
            "toll": 0,
            "traffic_lights": 0,
            "polyline": route.get("polyline", []),
        }

    def _format_coordinate(self, point: Dict[str, Any]) -> str:
        latitude = float(point.get("latitude") or point.get("lat"))
        longitude = float(point.get("longitude") or point.get("lng") or point.get("lon"))
        return f"{latitude},{longitude}"

    def _parse_lng_lat_text(self, value: str) -> Dict[str, float]:
        try:
            lng_text, lat_text = str(value).split(",")[:2]
            return {"latitude": float(lat_text), "longitude": float(lng_text)}
        except Exception as exc:
            raise RuntimeError("腾讯路线规划要求使用有效经纬度坐标，格式为 lng,lat") from exc

    def _decode_polyline(self, polyline: Any) -> List[Dict[str, float]]:
        if not isinstance(polyline, list) or len(polyline) < 2:
            return []

        if isinstance(polyline[0], dict):
            return [
                {
                    "latitude": float(point.get("latitude") or point.get("lat")),
                    "longitude": float(point.get("longitude") or point.get("lng") or point.get("lon")),
                }
                for point in polyline
                if point
            ]

        values = [float(value) for value in polyline]
        for index in range(2, len(values)):
            values[index] = values[index - 2] + values[index] / 1000000

        decoded = []
        for index in range(0, len(values) - 1, 2):
            decoded.append({
                "latitude": values[index],
                "longitude": values[index + 1],
            })
        return decoded


tencent_map_service = TencentMapService()


def search_pois(keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
    return tencent_map_service.search_pois(keyword, city, page, size)


def search_hotels(keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
    return tencent_map_service.search_hotels(keyword, city, page, size)


def calculate_route(origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
    return tencent_map_service.calculate_route(origin, destination, mode)
