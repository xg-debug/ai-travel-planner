import logging
from typing import Any, Dict, List

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


class TencentMapService:
    """腾讯位置服务：路线规划。"""

    def __init__(self) -> None:
        self.api_key = settings.TENCENT_MAP_API_KEY
        self.base_url = "https://apis.map.qq.com/ws/direction/v1"
        self.mode_paths = {
            "driving": "driving",
            "walking": "walking",
            "bicycling": "bicycling",
            "transit": "transit",
        }

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

    def _format_coordinate(self, point: Dict[str, Any]) -> str:
        latitude = float(point.get("latitude") or point.get("lat"))
        longitude = float(point.get("longitude") or point.get("lng") or point.get("lon"))
        return f"{latitude},{longitude}"

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
