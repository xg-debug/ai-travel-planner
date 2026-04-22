from app.tools.amap_tools import calculate_route_tool, search_hotels_tool, search_pois_tool
from app.tools.media_tools import search_photo_tool
from app.tools.weather_tools import get_weather_tool


TOOLS = {
    "search_pois": search_pois_tool,
    "search_hotels": search_hotels_tool,
    "calculate_route": calculate_route_tool,
    "get_weather": get_weather_tool,
    "search_photo": search_photo_tool,
}

