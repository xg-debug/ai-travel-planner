import requests
import logging
import re
import math
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        matched = re.search(r"-?\d+", text)
        if not matched:
            return default
        return int(matched.group())
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, (list, tuple)):
            for item in value:
                parsed = _safe_float(item, None)  # type: ignore[arg-type]
                if parsed is not None:
                    return parsed
            return default
        if isinstance(value, dict):
            for key in ("value", "rating", "score", "lat", "lng", "longitude", "latitude"):
                if key in value:
                    return _safe_float(value.get(key), default)
            return default
        text = str(value).strip()
        if not text:
            return default
        matched = re.search(r"-?\d+(?:\.\d+)?", text)
        if not matched:
            return default
        return float(matched.group())
    except Exception:
        return default


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return " ".join(parts) if parts else default
    if isinstance(value, dict):
        for key in ("value", "name", "text", "label"):
            if key in value:
                return _safe_text(value.get(key), default)
        return default
    text = str(value).strip()
    return text or default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_location(value: Any) -> tuple[float, float]:
    if isinstance(value, str):
        parts = value.split(",")
        if len(parts) >= 2:
            lng = _safe_float(parts[0], 0.0)
            lat = _safe_float(parts[1], 0.0)
            return lng, lat
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        lng = _safe_float(value[0], 0.0)
        lat = _safe_float(value[1], 0.0)
        return lng, lat
    if isinstance(value, dict):
        lng = _safe_float(value.get("lng") or value.get("lon") or value.get("longitude"), 0.0)
        lat = _safe_float(value.get("lat") or value.get("latitude"), 0.0)
        return lng, lat
    return 0.0, 0.0


def _is_valid_route_coordinate(value: str) -> bool:
    try:
        lng_text, lat_text = str(value).split(",")[:2]
        lng = float(lng_text)
        lat = float(lat_text)
        return 73 <= lng <= 136 and 3 <= lat <= 54
    except Exception:
        return False


def _estimate_direct_route(origin: str, destination: str) -> Dict[str, Any]:
    try:
        origin_lng, origin_lat = [float(item) for item in origin.split(",")[:2]]
        dest_lng, dest_lat = [float(item) for item in destination.split(",")[:2]]
    except Exception as exc:
        raise RuntimeError(f"无法估算直线路线: {exc}") from exc

    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)
        a = (
            math.sin(d_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        )
        return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = haversine(origin_lat, origin_lng, dest_lat, dest_lng)
    duration = max(int(distance / 8), 300)
    return {
        "distance": int(distance),
        "duration": duration,
        "steps": [
            {
                "instruction": "使用直连降级路线",
                "polyline": f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}",
            }
        ],
        "toll": 0,
        "traffic_lights": 0,
        "fallback": True,
    }

class AMapService:
    """高德地图服务"""
    
    def __init__(self):
        self.api_key = settings.AMAP_API_KEY
        self.base_url = "https://restapi.amap.com/v3"
        
    def search_pois(
        self,
        keyword: str,
        city: str,
        page: int = 1,
        size: int = 10,
        poi_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        搜索POI（兴趣点）
        
        Args:
            keyword: 搜索关键词
            city: 城市名称
            page: 页码
            size: 每页数量
            
        Returns:
            POI列表
        """
        if not self.api_key:
            raise RuntimeError("AMAP_API_KEY 未配置，无法搜索 POI")
        
        try:
            params = {
                "key": self.api_key,
                "keywords": keyword,
                "city": city,
                "output": "json",
                "offset": size,
                "page": page,
                "extensions": "all"
            }
            if poi_type:
                params["types"] = poi_type
            
            response = requests.get(f"{self.base_url}/place/text", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "1" and data.get("pois"):
                pois = []
                for poi in data["pois"][:size]:
                    biz_ext = _safe_dict(poi.get("biz_ext"))
                    photos = poi.get("photos") or []
                    image_url = ""
                    if photos and isinstance(photos, list):
                        image_url = photos[0].get("url", "") or ""
                    lng, lat = _parse_location(poi.get("location"))
                    pois.append({
                        "id": poi.get("id"),
                        "name": _safe_text(poi.get("name")),
                        "lat": lat,
                        "lng": lng,
                        "address": _safe_text(poi.get("address"), city),
                        "type": _safe_text(poi.get("type")),
                        "rating": _safe_float(biz_ext.get("rating"), 4.0) or 4.0,
                        "price": _safe_text(biz_ext.get("cost"), "免费"),
                        "description": f"{_safe_text(poi.get('name'))}位于{_safe_text(poi.get('address'), city)}",
                        "opening_hours": _safe_text(biz_ext.get("opentime"), "09:00-17:00"),
                        "image_url": image_url,
                        "best_time": "上午",
                        "tips": "建议提前查询最新信息"
                    })
                return pois
            else:
                logger.warning(f"No POIs found for {keyword} in {city}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching POIs: {e}")
            raise

    def search_hotels(self, keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
        """
        酒店搜索专用封装。
        仍基于高德 POI 搜索，但附加酒店类型过滤，适合当前免费方案。
        """
        hotel_queries = [keyword, f"{city}酒店", f"{city}宾馆"]
        results: List[Dict[str, Any]] = []
        seen = set()
        for hotel_query in hotel_queries:
            pois = self.search_pois(hotel_query, city, page, size, poi_type="住宿服务")
            for poi in pois:
                name = _safe_text(poi.get("name"))
                if not name or name in seen:
                    continue
                seen.add(name)
                results.append(poi)
                if len(results) >= size:
                    return results
        return results
    
    def get_weather_forecast(self, city: str, days: int = 3) -> Dict[str, Any]:
        """
        获取天气预报
        
        Args:
            city: 城市名称
            days: 预报天数
            
        Returns:
            天气预报数据
        """
        if not self.api_key:
            raise RuntimeError("AMAP_API_KEY 未配置，无法查询天气")
        
        try:
            # 先获取城市编码
            city_params = {
                "key": self.api_key,
                "keywords": city,
                "subdistrict": 0
            }
            
            city_response = requests.get(f"{self.base_url}/config/district", params=city_params, timeout=10)
            city_response.raise_for_status()
            city_data = city_response.json()
            
            if city_data.get("status") == "1" and city_data.get("districts"):
                adcode = city_data["districts"][0].get("adcode")
                
                # 获取天气
                weather_params = {
                    "key": self.api_key,
                    "city": adcode,
                    "extensions": "all" if days > 1 else "base"
                }
                
                weather_response = requests.get(f"{self.base_url}/weather/weatherInfo", params=weather_params, timeout=10)
                weather_response.raise_for_status()
                weather_data = weather_response.json()
                
                if weather_data.get("status") == "1":
                    return self._parse_weather_data(weather_data, city, days)
                else:
                    raise RuntimeError(f"城市 {city} 的天气数据不可用")
            else:
                raise RuntimeError(f"未找到城市编码: {city}")
                
        except Exception as e:
            logger.error(f"Error getting weather: {e}")
            raise
    
    def calculate_route(self, origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
        """
        计算路线
        
        Args:
            origin: 起点坐标或地址
            destination: 终点坐标或地址
            mode: 交通方式 (driving, walking, transit, bicycling)
            
        Returns:
            路线信息
        """
        if not self.api_key:
            raise RuntimeError("AMAP_API_KEY 未配置，无法计算路线")
        
        try:
            if _is_valid_route_coordinate(origin) and _is_valid_route_coordinate(destination):
                params = {
                    "key": self.api_key,
                    "origin": origin,
                    "destination": destination,
                    "strategy": self._get_route_strategy(mode)
                }

                response = requests.get(f"{self.base_url}/direction/{mode}", params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "1" and data.get("route", {}).get("paths"):
                    route = data["route"]["paths"][0]
                    return {
                        "distance": route.get("distance", 0),
                        "duration": route.get("duration", 0),
                        "steps": route.get("steps", []),
                        "toll": route.get("toll", 0),
                        "traffic_lights": route.get("traffic_lights", 0)
                    }

                logger.warning("AMap route not found, fallback to direct line: %s -> %s", origin, destination)
                return _estimate_direct_route(origin, destination)

            params = {
                "key": self.api_key,
                "origin": origin,
                "destination": destination,
                "strategy": self._get_route_strategy(mode)
            }
            
            response = requests.get(f"{self.base_url}/direction/{mode}", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "1" and data.get("route"):
                route = data["route"]["paths"][0]
                return {
                    "distance": route.get("distance", 0),
                    "duration": route.get("duration", 0),
                    "steps": route.get("steps", []),
                    "toll": route.get("toll", 0),
                    "traffic_lights": route.get("traffic_lights", 0)
                }
            else:
                raise RuntimeError(f"未找到从 {origin} 到 {destination} 的路线")
                
        except Exception as e:
            logger.error(f"Error calculating route: {e}")
            if _is_valid_route_coordinate(origin) and _is_valid_route_coordinate(destination):
                return _estimate_direct_route(origin, destination)
            raise
    
    def _parse_weather_data(self, weather_data: Dict[str, Any], city: str, days: int) -> Dict[str, Any]:
        """解析天气数据"""
        result = {
            "city": city,
            "report_time": weather_data.get("forecasts", [{}])[0].get("reporttime", ""),
            "forecast": []
        }
        
        forecasts = weather_data.get("forecasts", [])
        if forecasts:
            casts = forecasts[0].get("casts", [])
            for i, cast in enumerate(casts[:days]):
                result["forecast"].append({
                    "date": cast.get("date", ""),
                    "condition": self._translate_weather(cast.get("dayweather", "")),
                    "temperature": {
                        "min": _safe_int(cast.get("nighttemp"), 0),
                        "max": _safe_int(cast.get("daytemp"), 0),
                        "avg": (_safe_int(cast.get("nighttemp"), 0) + _safe_int(cast.get("daytemp"), 0)) // 2
                    },
                    "humidity": _safe_int(cast.get("dayhumidity"), 60),
                    "wind_speed": _safe_int(cast.get("daypower"), 3),
                    "icon": self._get_weather_icon(cast.get("dayweather", ""))
                })
        
        return result
    
    def _translate_weather(self, weather: str) -> str:
        """翻译天气描述"""
        translations = {
            "晴": "晴朗",
            "多云": "多云",
            "阴": "阴天",
            "雨": "下雨",
            "雪": "下雪",
            "雾": "有雾",
            "霾": "雾霾"
        }
        return translations.get(weather, weather)
    
    def _get_weather_icon(self, weather: str) -> str:
        """获取天气图标"""
        icons = {
            "晴": "sunny",
            "多云": "cloudy",
            "阴": "cloudy",
            "雨": "rainy",
            "雪": "snowy",
            "雾": "foggy",
            "霾": "hazy"
        }
        return icons.get(weather, "unknown")
    
    def _get_route_strategy(self, mode: str) -> int:
        """获取路线策略"""
        strategies = {
            "driving": 0,  # 速度优先
            "walking": 0,  # 最短路径
            "transit": 0,  # 最快捷
            "bicycling": 0  # 最短路径
        }
        return strategies.get(mode, 0)
    
# 创建服务实例
amap_service = AMapService()

# 导出函数
def search_pois(keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
    return amap_service.search_pois(keyword, city, page, size)

def search_hotels(keyword: str, city: str, page: int = 1, size: int = 10) -> List[Dict[str, Any]]:
    return amap_service.search_hotels(keyword, city, page, size)

def get_weather_forecast(city: str, days: int = 3) -> Dict[str, Any]:
    return amap_service.get_weather_forecast(city, days)

def calculate_route(origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
    return amap_service.calculate_route(origin, destination, mode)
