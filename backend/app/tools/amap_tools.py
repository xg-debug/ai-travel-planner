from typing import Any, Dict, List

from app.services.amap_service import calculate_route, search_hotels, search_pois


def search_pois_tool(keyword: str, city: str, size: int = 8) -> List[Dict[str, Any]]:
    return search_pois(keyword, city, 1, size)


def search_hotels_tool(keyword: str, city: str, size: int = 8) -> List[Dict[str, Any]]:
    return search_hotels(keyword, city, 1, size)


def calculate_route_tool(origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
    return calculate_route(origin, destination, mode)

