import unittest
from unittest.mock import Mock, patch

from app.domain.travel_domain import TravelDomainService
from app.services.amap_road_routes import fetch_road_route
from app.mcp_tools.amap_provider import AMapMCPError
from app.services.runtime_config import LLM_PROVIDERS, get_llm_provider


class RoadRouteTests(unittest.TestCase):
    def test_original_model_providers_and_retired_provider_defaults_to_deepseek(self):
        self.assertEqual(set(LLM_PROVIDERS), {'deepseek', 'openai', 'anthropic', 'google'})
        with patch('app.services.runtime_config.get_runtime_setting', return_value='retired-provider'):
            self.assertEqual(get_llm_provider(), 'deepseek')

    def test_geometry_supplement_requires_opt_in_and_keeps_one_consistent_route(self):
        service = TravelDomainService()
        mcp_route = {'distance': 10, 'duration': 20, 'instructions': ['MCP'], 'geometry_available': False}
        road_route = {'distance': 1200, 'duration': 900, 'instructions': ['沿道路行驶'], 'geometry_available': True,
                      'provider': 'amap_web_service', 'polylines': [[{'latitude': 30, 'longitude': 120}, {'latitude': 30.1, 'longitude': 120.1}]]}
        provider = Mock(); provider.call_tool.return_value = mcp_route
        with patch.object(service.registry, 'get', return_value=provider), \
                patch('app.domain.travel_domain.get_map_provider', return_value='amap_mcp'), \
                patch('app.domain.travel_domain.get_cache', return_value=None), \
                patch('app.domain.travel_domain.set_cache'), \
                patch('app.services.amap_road_routes.fetch_road_route', return_value=road_route) as fetch:
            with patch('app.domain.travel_domain.settings.AMAP_ROAD_GEOMETRY_ENABLED', False):
                self.assertEqual(service.calculate_route('120,30', '120.1,30.1')['distance'], 10)
                fetch.assert_not_called()
            with patch('app.domain.travel_domain.settings.AMAP_ROAD_GEOMETRY_ENABLED', True):
                result = service.calculate_route('120,30', '120.1,30.1')
                self.assertEqual(result['distance'], 1200)
                self.assertEqual(result['duration'], 900)
                self.assertEqual(result['instructions'], ['沿道路行驶'])
                self.assertTrue(result['geometry_available'])

    def test_four_modes_parse_real_geometry_shapes_without_bridging_steps(self):
        paths = [{'distance': '1200', 'duration': '900', 'steps': [
            {'instruction': '沿路步行', 'polyline': '120,30;120.001,30.002;120.002,30.003'},
            {'instruction': '继续向前', 'polyline': '120.002,30.003;120.004,30.004'},
        ]}]
        for mode in ('walking', 'driving', 'bicycling', 'transit'):
            data = {'route': {'paths': paths}, 'status': '1'}
            if mode == 'bicycling': data = {'data': {'paths': paths}, 'errcode': 0}
            if mode == 'transit': data = {'status': '1', 'route': {'transits': [{'distance': '1200', 'duration': '900', 'segments': [{'walking': {'steps': paths[0]['steps']}}]}]}}
            client = Mock(); client.get.return_value.json.return_value = data
            with patch('app.services.amap_road_routes.get_map_api_key', return_value='fake-unit-key'), \
                    patch('app.services.amap_road_routes.time.sleep'), \
                    patch('app.services.amap_road_routes.httpx.Client') as factory:
                factory.return_value.__enter__.return_value = client
                result = fetch_road_route('120,30', '120.004,30.004', mode, '杭州')
            self.assertEqual(len(result['polylines']), 2)
            self.assertEqual(len(result['polylines'][0]), 3)
            self.assertEqual(result['polyline'], [])
            self.assertEqual(result['provider'], 'amap_web_service')
            self.assertEqual(result['coordinate_system'], 'GCJ02')
            self.assertEqual(result['distance'], 1200)
            self.assertEqual(client.get.call_args.kwargs['params']['key'], 'fake-unit-key')

    def test_mcp_outage_can_use_authorized_road_service(self):
        service = TravelDomainService()
        provider = Mock()
        provider.call_tool.side_effect = AMapMCPError('MCP unavailable')
        road_route = {'distance': 1200, 'duration': 900, 'provider': 'amap_web_service', 'geometry_available': True,
                      'polylines': [[{'latitude': 30, 'longitude': 120}, {'latitude': 30.1, 'longitude': 120.1}]]}
        with patch.object(service.registry, 'get', return_value=provider), \
                patch('app.domain.travel_domain.get_map_provider', return_value='amap_mcp'), \
                patch('app.domain.travel_domain.get_cache', return_value=None), \
                patch('app.domain.travel_domain.set_cache'), \
                patch('app.domain.travel_domain.settings.AMAP_ROAD_GEOMETRY_ENABLED', True), \
                patch('app.services.amap_road_routes.fetch_road_route', return_value=road_route) as fetch:
            self.assertTrue(service.calculate_route('120,30', '120.1,30.1')['geometry_available'])
            fetch.side_effect = AMapMCPError('REST unavailable')
            with self.assertRaises(AMapMCPError):
                service.calculate_route('120,30', '120.1,30.1')

    def test_failed_geometry_is_not_cached_so_manual_retry_can_recover(self):
        service = TravelDomainService()
        provider = Mock()
        provider.call_tool.return_value = {'distance': 100, 'duration': 200, 'geometry_available': False}
        with patch.object(service.registry, 'get', return_value=provider), \
                patch('app.domain.travel_domain.get_map_provider', return_value='amap_mcp'), \
                patch('app.domain.travel_domain.get_cache', return_value=None), \
                patch('app.domain.travel_domain.set_cache') as cache, \
                patch('app.domain.travel_domain.settings.AMAP_ROAD_GEOMETRY_ENABLED', True), \
                patch('app.services.amap_road_routes.fetch_road_route', side_effect=AMapMCPError('temporary')):
            result = service.calculate_route('120,30', '120.1,30.1')
            self.assertFalse(result['geometry_available'])
            self.assertEqual(result['distance'], 100)
            cache.assert_not_called()

    def test_road_error_does_not_leak_credential_url_or_invent_geometry(self):
        client = Mock(); client.get.side_effect = RuntimeError('https://restapi.amap.com?key=private-key')
        with patch('app.services.amap_road_routes.get_map_api_key', return_value='fake-unit-key'), \
                patch('app.services.amap_road_routes.time.sleep'), \
                patch('app.services.amap_road_routes.httpx.Client') as factory:
            factory.return_value.__enter__.return_value = client
            with self.assertRaises(AMapMCPError) as error:
                fetch_road_route('120,30', '120.004,30.004', 'walking')
        self.assertNotIn('private-key', str(error.exception))


if __name__ == '__main__': unittest.main()
