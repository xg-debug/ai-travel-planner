from typing import Any, Dict

from app.domain import travel_domain_service


def get_weather_tool(city: str, days: int) -> Dict[str, Any]:
    return travel_domain_service.get_weather(city, days)
