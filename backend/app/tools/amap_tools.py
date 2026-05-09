from typing import Any, Dict, List

from app.domain import travel_domain_service


def search_pois_tool(keyword: str, city: str, size: int = 8) -> List[Dict[str, Any]]:
    return travel_domain_service.search_pois(keyword, city, 1, size)


def search_hotels_tool(keyword: str, city: str, size: int = 8) -> List[Dict[str, Any]]:
    return travel_domain_service.search_hotels(keyword, city, 1, size)


def calculate_route_tool(origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
    return travel_domain_service.calculate_route(origin, destination, mode)
