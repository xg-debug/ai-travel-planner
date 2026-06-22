import logging
import math
from typing import Any, Dict, List

from app.services.amap_service import amap_service
from app.services.runtime_config import get_map_api_key, is_present_secret
from app.services.tencent_map_service import tencent_map_service

logger = logging.getLogger(__name__)


def available_route_providers() -> List[str]:
    providers: List[str] = []
    if is_present_secret(get_map_api_key("tencent")):
        providers.append("tencent")
    if is_present_secret(get_map_api_key("amap")):
        providers.append("amap")
    return providers


def plan_day_map_route(points: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
    if len(points) < 2:
        return {"distance": 0, "duration": 0, "polyline": [], "legs": [], "provider": "none"}

    providers = available_route_providers()
    if not providers:
        logger.warning("No map route provider configured, fallback to straight point polylines")

    legs: List[Dict[str, Any]] = []
    merged_polyline: List[Dict[str, float]] = []
    total_distance = 0
    total_duration = 0
    used_providers: List[str] = []
    failed_legs = 0

    for index in range(len(points) - 1):
        leg = _plan_route_segment(points[index], points[index + 1], mode, providers)
        leg["fromIndex"] = index
        leg["toIndex"] = index + 1
        legs.append(leg)
        total_distance += int(leg.get("distance", 0) or 0)
        total_duration += int(leg.get("duration", 0) or 0)
        provider = str(leg.get("provider") or "")
        if provider == "fallback" or len(leg.get("polyline", []) or []) < 2:
            failed_legs += 1
        if provider and provider not in used_providers:
            used_providers.append(provider)
        _merge_polyline(merged_polyline, leg.get("polyline", []) or [])

    return {
        "distance": total_distance,
        "duration": total_duration,
        "polyline": merged_polyline,
        "legs": legs,
        "provider": ",".join(used_providers) or "fallback",
        "partial": failed_legs > 0,
        "warning": "部分路段未获取到真实道路路线，已隐藏直线兜底。" if failed_legs else "",
    }


def _plan_route_segment(origin: Dict[str, Any], destination: Dict[str, Any], mode: str, providers: List[str]) -> Dict[str, Any]:
    errors: List[str] = []
    route_modes = _route_modes_for_segment(origin, destination, mode)
    for route_mode in route_modes:
        for provider in providers:
            try:
                if provider == "tencent":
                    return _plan_tencent_segment(origin, destination, route_mode)
                if provider == "amap":
                    return _plan_amap_segment(origin, destination, route_mode)
            except Exception as exc:
                errors.append(f"{provider}/{route_mode}: {exc}")
                logger.info("Route provider skipped provider=%s mode=%s error=%s", provider, route_mode, exc)
    return {
        "distance": int(_coordinate_distance_meters(origin, destination)),
        "duration": 0,
        "polyline": [],
        "provider": "fallback",
        "error": " | ".join(errors) if errors else "未配置可用地图路线规划 Key，无法生成真实道路路线",
    }


def _plan_tencent_segment(origin: Dict[str, Any], destination: Dict[str, Any], mode: str) -> Dict[str, Any]:
    route = tencent_map_service.plan_segment(origin, destination, mode)
    polyline = route.get("polyline", []) or []
    if len(polyline) < 2:
        raise RuntimeError("腾讯地图未返回可绘制路线")
    return {
        "distance": int(route.get("distance", 0) or 0),
        "duration": int(route.get("duration", 0) or 0),
        "polyline": polyline,
        "provider": "tencent",
    }


def _plan_amap_segment(origin: Dict[str, Any], destination: Dict[str, Any], mode: str) -> Dict[str, Any]:
    route_mode = mode if mode in {"driving", "walking", "bicycling", "transit"} else "driving"
    route = amap_service.calculate_route(_format_amap_point(origin), _format_amap_point(destination), route_mode)
    polyline = _parse_amap_step_polyline(route.get("steps", []) or [])
    if len(polyline) < 2:
        raise RuntimeError("高德地图未返回可绘制路线")
    return {
        "distance": int(route.get("distance", 0) or 0),
        "duration": int(route.get("duration", 0) or 0),
        "polyline": polyline,
        "provider": "amap",
    }


def _route_modes_for_segment(origin: Dict[str, Any], destination: Dict[str, Any], mode: str) -> List[str]:
    requested = mode if mode in {"driving", "walking", "bicycling"} else ""
    distance = _coordinate_distance_meters(origin, destination)
    if mode == "touring" or not requested:
        preferred = ["walking", "bicycling", "driving"] if distance <= 3500 else ["driving", "bicycling", "walking"]
    else:
        preferred = [requested]
    result: List[str] = []
    for item in [*preferred, "walking", "driving", "bicycling"]:
        if item not in result:
            result.append(item)
    return result


def _merge_polyline(target: List[Dict[str, float]], source: List[Dict[str, float]]) -> None:
    if not source:
        return
    if target:
        target.extend(source[1:])
    else:
        target.extend(source)


def _coordinate_distance_meters(origin: Dict[str, Any], destination: Dict[str, Any]) -> float:
    origin_lat = float(origin.get("latitude") or origin.get("lat") or 0)
    origin_lng = float(origin.get("longitude") or origin.get("lng") or origin.get("lon") or 0)
    dest_lat = float(destination.get("latitude") or destination.get("lat") or 0)
    dest_lng = float(destination.get("longitude") or destination.get("lng") or destination.get("lon") or 0)
    if not origin_lat or not origin_lng or not dest_lat or not dest_lng:
        return 0.0
    radius = 6371000
    d_lat = math.radians(dest_lat - origin_lat)
    d_lng = math.radians(dest_lng - origin_lng)
    lat1 = math.radians(origin_lat)
    lat2 = math.radians(dest_lat)
    hav = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(hav))


def _format_amap_point(point: Dict[str, Any]) -> str:
    latitude = float(point.get("latitude") or point.get("lat") or 0)
    longitude = float(point.get("longitude") or point.get("lng") or point.get("lon") or 0)
    return f"{longitude},{latitude}"


def _parse_amap_step_polyline(steps: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    points: List[Dict[str, float]] = []
    for step in steps or []:
        for pair in str(step.get("polyline", "") or "").split(";"):
            values = pair.split(",")
            if len(values) < 2:
                continue
            try:
                points.append({"latitude": float(values[1]), "longitude": float(values[0])})
            except ValueError:
                continue
    return points
