from typing import Any, Dict

from app.services.amap_service import get_weather_forecast


def get_weather_tool(city: str, days: int) -> Dict[str, Any]:
    return get_weather_forecast(city, days)

