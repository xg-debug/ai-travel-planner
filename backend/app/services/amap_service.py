"""Compatibility facade. All AMap capabilities are served by official HTTP MCP."""
from app.mcp_tools.amap_provider import AMapMCPProvider

class AMapService:
    def __init__(self):
        self.provider = AMapMCPProvider()

    def search_pois(self, keyword, city, page=1, size=10, poi_type=None):
        return self.provider.call_tool('geocode_pois', dict(keyword=keyword, city=city, page=page, size=size))

    def get_weather_forecast(self, city, days=3):
        return self.provider.call_tool('get_weather_forecast', dict(city=city, days=days))

    def calculate_route(self, origin, destination, mode='driving', city='', cityd=''):
        return self.provider.call_tool('plan_route', dict(origin=origin, destination=destination, mode=mode, city=city, cityd=cityd))

amap_service = AMapService()
search_pois = amap_service.search_pois
get_weather_forecast = amap_service.get_weather_forecast
calculate_route = amap_service.calculate_route
