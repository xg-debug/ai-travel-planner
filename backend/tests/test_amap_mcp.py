from __future__ import annotations
import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch
from fastapi import HTTPException
from mcp.types import CallToolResult, TextContent
from pydantic import ValidationError
from app.api.map_routes import MapExportRequest, MapRouteRequest, export_personal_map
from app.domain.travel_domain import MapExportValidationError, TravelDomainService
from app.mcp_tools.amap_provider import AMapMCPProvider, AMapMCPError, MCPRateLimiter, coordinate, mcp_connection, safe_map_link
from app.services.map_route_service import plan_day_map_route
from app.services.runtime_config import get_map_provider
from app.trip_planning.tool_executor import TripPlanningToolbox


def response(data, error=False):
    return CallToolResult(content=[TextContent(type='text', text=json.dumps(data))], isError=error)


class AMapMCPTests(unittest.TestCase):
    def setUp(self):
        self.provider = AMapMCPProvider()
        limiter = patch('app.mcp_tools.amap_provider._rate_limiter.wait', new_callable=AsyncMock)
        limiter.start()
        self.addCleanup(limiter.stop)

    def test_limiter_spaces_calls_across_sessions(self):
        limiter = MCPRateLimiter()
        with patch('app.mcp_tools.amap_provider.time.monotonic', return_value=100), patch('app.mcp_tools.amap_provider.settings.AMAP_MCP_MAX_QPS', 2):
            self.assertEqual([limiter.reserve_delay() for _ in range(4)], [0, 0.5, 1, 1.5])

    def test_qps_failure_is_retried_for_reads(self):
        limited = CallToolResult(content=[TextContent(type='text', text='API 调用失败：CUQPS_HAS_EXCEEDED_THE_LIMIT')], isError=True)
        session = type('S', (), {'call_tool': AsyncMock(side_effect=[limited, response({'id': 'B123'})])})()
        with patch('app.mcp_tools.amap_provider.asyncio.sleep', new_callable=AsyncMock):
            result = asyncio.run(self.provider._call(session, 'maps_search_detail', {'id': 'B123'}))
        self.assertEqual(result['id'], 'B123')
        self.assertEqual(session.call_tool.await_count, 2)

    def test_exports_and_permanent_errors_are_not_replayed(self):
        for tool, text in [('maps_schema_personal_map', 'CUQPS_HAS_EXCEEDED_THE_LIMIT'), ('maps_search_detail', 'INVALID_USER_KEY')]:
            failure = CallToolResult(content=[TextContent(type='text', text=text)], isError=True)
            session = type('S', (), {'call_tool': AsyncMock(return_value=failure)})()
            with self.assertRaises(AMapMCPError):
                asyncio.run(self.provider._call(session, tool, {}))
            self.assertEqual(session.call_tool.await_count, 1)

    def test_search_hydrates_official_sparse_results_and_preserves_photo(self):
        async def call(session, name, args):
            if name == 'maps_text_search':
                return {'pois': [{'id': 'B123', 'name': '餐厅', 'photo': 'https://example.com/photo.jpg'}]}
            self.assertEqual((name, args), ('maps_search_detail', {'id': 'B123'}))
            return {'id': 'B123', 'name': '餐厅', 'location': '120.12,30.23', 'address': '湖滨路', 'type': '餐饮服务', 'cost': '80', 'rating': '4.8', 'open_time': '10:00-21:00'}
        @asynccontextmanager
        async def transport(*args, **kwargs): yield None, None, None
        @asynccontextmanager
        async def session(*args, **kwargs):
            class S:
                async def initialize(self): pass
            yield S()
        with patch('app.mcp_tools.amap_provider.mcp_connection', return_value=('https://mcp.amap.com/mcp', {})), patch('app.mcp_tools.amap_provider.streamablehttp_client', transport), patch('app.mcp_tools.amap_provider.ClientSession', session), patch.object(self.provider, '_call', side_effect=call), patch('app.mcp_tools.amap_provider.get_cache', return_value=None), patch('app.mcp_tools.amap_provider.set_cache'):
            result = self.provider.call_tool('geocode_pois', {'keyword': '餐厅', 'city': '杭州', 'size': 2})
        self.assertEqual(result[0]['lng'], 120.12)
        self.assertEqual(result[0]['address'], '湖滨路')
        self.assertEqual(result[0]['avg_cost'], 80)
        self.assertEqual(result[0]['opening_hours'], '10:00-21:00')
        self.assertEqual(result[0]['image_url'], 'https://example.com/photo.jpg')
        self.assertTrue(result[0]['verified'])

    def test_weather_and_transit_official_arguments(self):
        calls = []
        @asynccontextmanager
        async def transport(*args, **kwargs): yield None, None, None
        @asynccontextmanager
        async def session(*args, **kwargs):
            class S:
                async def initialize(self): pass
                async def call_tool(self, name, args):
                    calls.append((name, args))
                    if name == 'maps_weather':
                        return response({'city': '杭州', 'forecasts': [{'date': '2026-09-05', 'daytemp': '30', 'nighttemp': '24', 'dayweather': '晴'}]})
                    return response({'distance': '5000', 'transits': [{'duration': '1800', 'segments': [{'bus': {'buslines': [{'name': '地铁1号线', 'departure_stop': {'name': 'A'}, 'arrival_stop': {'name': 'B'}}]}}]}]})
            yield S()
        with patch('app.mcp_tools.amap_provider.mcp_connection', return_value=('https://mcp.amap.com/mcp', {})), patch('app.mcp_tools.amap_provider.streamablehttp_client', transport), patch('app.mcp_tools.amap_provider.ClientSession', session):
            weather = self.provider.call_tool('get_weather_forecast', {'city': '杭州', 'days': 7})
            route = self.provider.call_tool('plan_route', {'origin': '120,30', 'destination': '120.1,30.1', 'mode': 'transit', 'city': '杭州', 'cityd': '杭州'})
        self.assertEqual(len(weather['forecast']), 1)  # Never fabricate extra forecast days.
        self.assertEqual(calls[1][1]['cityd'], '杭州')
        self.assertEqual(route['duration'], 1800)
        self.assertEqual(route['distance'], 5000)
        self.assertIn('地铁1号线', route['instructions'][0])
        self.assertFalse(route['geometry_available'])

    def test_route_without_polyline_still_keeps_verified_metrics(self):
        result = self.provider._route({'route': {'paths': [{'distance': 1200, 'duration': 900, 'steps': [{'instruction': '向北步行'}]}]}}, 'walking')
        with patch('app.services.map_route_service.travel_domain_service.calculate_route', return_value=result) as call:
            plan = plan_day_map_route([{'latitude': 30, 'longitude': 120}, {'latitude': 30.01, 'longitude': 120.01}], 'walking')
        call.assert_called_once()
        self.assertEqual(plan['distance'], 1200)
        self.assertFalse(plan['partial'])
        self.assertTrue(plan['legs'][0]['ok'])
        self.assertFalse(plan['geometry_available'])
        self.assertEqual(plan['polyline'], [])

    def test_explicit_mode_failure_does_not_silently_switch_transport(self):
        with patch('app.services.map_route_service.travel_domain_service.calculate_route', side_effect=AMapMCPError('不可用')) as call:
            result = plan_day_map_route([{'latitude': 30, 'longitude': 120}, {'latitude': 30.1, 'longitude': 120.1}], 'bicycling')
        call.assert_called_once()
        self.assertTrue(result['partial'])
        self.assertEqual(result['distance'], 0)
        self.assertEqual(result['legs'][0]['mode'], 'bicycling')

    def test_nested_route_geometry_keeps_separate_groups(self):
        result = self.provider._route({'paths': [{'steps': [{'polyline': '120,30;120.1,30.1'}, {'polyline': '121,31;121.1,31.1'}]}]}, 'walking')
        self.assertEqual(len(result['polylines']), 2)
        self.assertEqual(result['polyline'], [])  # No invented bridge between separate geometries.

    def test_error_results_and_transport_failures_are_not_data_or_secret_leaks(self):
        session = type('S', (), {'call_tool': AsyncMock(return_value=response({'secret': 'private'}, True))})()
        with self.assertRaises(AMapMCPError):
            asyncio.run(self.provider._call(session, 'maps_weather', {}))
        with patch.object(self.provider, '_dispatch', side_effect=ExceptionGroup('request', [RuntimeError('https://mcp.amap.com/mcp?key=secret')])):
            with self.assertRaises(AMapMCPError) as raised:
                self.provider.call_tool('get_weather_forecast', {'city': '杭州'})
        self.assertNotIn('secret', str(raised.exception))

    def test_legacy_config_uses_http_and_rejects_foreign_credential_destination(self):
        with patch('app.services.runtime_config.get_runtime_setting', return_value='amap_mcp_sse'):
            self.assertEqual(get_map_provider(), 'amap_mcp')
        with patch('app.mcp_tools.amap_provider.get_amap_mcp_url', return_value='https://example.com/mcp'):
            with self.assertRaises(AMapMCPError): mcp_connection()

    def test_export_preserves_day_order_coordinates_and_poi_ids(self):
        request = MapExportRequest(title='杭州两日游', segments=[{'dayIndex': 0, 'points': [{'latitude': 30, 'longitude': 120, 'title': '景点', 'poiId': 'B123'}]}, {'dayIndex': 1, 'points': [{'latitude': 31, 'longitude': 121, 'title': '酒店', 'poiId': 'B456'}]}])
        with patch('app.api.map_routes.travel_domain_service.export_map', return_value={'url': 'amapuri://workInAmap/createWithToken?x=1'}) as call:
            export_personal_map(request)
        days = call.call_args.args[1]
        self.assertEqual(days[1]['pointInfoList'][0]['poiId'], 'B456')
        self.assertEqual(days[0]['pointInfoList'][0]['lon'], 120)
        self.assertEqual(safe_map_link({'text': 'amapuri://workInAmap/createWithToken?x=1'}), 'amapuri://workInAmap/createWithToken?x=1')
        for value in ('javascript:alert(1)', 'https://evil.example/map', 'https://amap.com.evil.example/map'):
            with self.assertRaises(AMapMCPError): safe_map_link(value)

    def test_validation_blocks_invalid_coordinates_and_unbounded_requests(self):
        for value in ('nan,30', '181,30', 'foo', '120,91'):
            with self.assertRaises(ValueError): coordinate(value)
        with self.assertRaises(ValidationError): MapRouteRequest(mode='flight')
        with self.assertRaises(ValidationError): MapExportRequest(title='x', segments=[])

    def test_export_recovers_only_verified_unique_nearby_poi_without_mutating_trip(self):
        service = TravelDomainService()
        days = [{'title': '第一天', 'pointInfoList': [{'name': '雷峰塔', 'lat': 30.23, 'lon': 120.15, 'poiId': ''}]}]
        poi = {'id': 'B123', 'name': '雷峰塔', 'lat': 30.2301, 'lng': 120.15, 'verified': True}
        provider = Mock()
        with patch.object(service, 'search_around', return_value=[poi]), patch.object(service.registry, 'get', return_value=provider):
            service.export_map('杭州', days)
        self.assertEqual(provider.call_tool.call_args.args[1]['lineList'][0]['pointInfoList'][0]['poiId'], 'B123')
        self.assertEqual(days[0]['pointInfoList'][0]['poiId'], '')
        for candidates in ([], [{**poi, 'verified': False}], [{**poi, 'lat': 31}], [poi, {**poi, 'id': 'B456'}], [{**poi, 'name': '雷峰塔停车场'}]):
            provider.reset_mock()
            with patch.object(service, 'search_around', return_value=candidates), patch.object(service.registry, 'get', return_value=provider):
                with self.assertRaises(MapExportValidationError):
                    service.export_map('杭州', days)
            provider.call_tool.assert_not_called()

    def test_export_missing_id_returns_actionable_validation_error(self):
        request = MapExportRequest(title='杭州', segments=[{'points': [{'latitude': 30, 'longitude': 120, 'title': '旧地点'}]}])
        with patch('app.api.map_routes.travel_domain_service.export_map', side_effect=MapExportValidationError('旧地点未能核对')):
            with self.assertRaises(HTTPException) as error:
                export_personal_map(request)
        self.assertEqual(error.exception.status_code, 422)
        self.assertIn('旧地点', error.exception.detail)

    def test_nearby_food_uses_both_attraction_and_hotel_coordinates(self):
        foods = [{'id': f'B{i}', 'name': f'本地餐厅{i}', 'lat': 30, 'lng': 120, 'source': 'amap_mcp', 'type': '餐饮服务'} for i in range(6)]
        with patch('app.trip_planning.tool_executor.travel_domain_service.search_around', return_value=foods) as around, patch('app.trip_planning.tool_executor._search_many') as city_search:
            result = TripPlanningToolbox().search_foods({'city': '杭州', 'attraction_candidates': [{'name': '西湖', 'lng': 120, 'lat': 30}], 'hotel_options': [{'name': '酒店', 'lng': 121, 'lat': 31}]}, {})
        self.assertEqual(around.call_count, 2)
        city_search.assert_not_called()
        self.assertTrue(result['food_candidates'])

    def test_shared_route_cache_is_separated_by_mode_and_transit_city(self):
        service = TravelDomainService()
        provider = type('P', (), {'call_tool': lambda self, *args: {'distance': 1, 'instructions': ['公交']}})()
        with patch.object(service.registry, 'get', return_value=provider), patch('app.domain.travel_domain.get_cache', return_value=None) as read, patch('app.domain.travel_domain.set_cache'), patch('app.domain.travel_domain.settings.AMAP_ROAD_GEOMETRY_ENABLED', False):
            service.calculate_route('120,30', '121,31', 'transit', '杭州', '上海')
            service.calculate_route('120.0,30.0', '121,31', 'transit', '杭州', '南京')
        self.assertNotEqual(read.call_args_list[0], read.call_args_list[1])

if __name__ == '__main__': unittest.main()
