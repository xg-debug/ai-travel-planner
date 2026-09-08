"""Optional official road geometry, used only when explicitly enabled."""
from __future__ import annotations

import logging
import time
import httpx

from app.mcp_tools.amap_provider import AMapMCPError, AMapMCPProvider, coordinate, _rate_limiter
from app.services.runtime_config import get_map_api_key

logger = logging.getLogger(__name__)
ENDPOINTS = {
    'walking': 'v3/direction/walking',
    'driving': 'v3/direction/driving',
    'bicycling': 'v4/direction/bicycling',
    'transit': 'v3/direction/transit/integrated',
}


def fetch_road_route(origin: str, destination: str, mode: str, city: str = '', cityd: str = '') -> dict:
    if mode not in ENDPOINTS:
        raise ValueError('不支持的交通方式')
    key = get_map_api_key('amap_mcp')
    if not key:
        raise AMapMCPError('道路路线需要配置高德 Web 服务 Key')
    params = {'key': key, 'origin': coordinate(origin), 'destination': coordinate(destination), 'output': 'JSON'}
    if mode == 'transit':
        if not city:
            raise ValueError('公交路线需要城市')
        params.update(city=city, cityd=cityd or city, extensions='all')
    elif mode == 'driving':
        params['extensions'] = 'all'
    for attempt in range(3):
        time.sleep(_rate_limiter.reserve_delay())
        try:
            with httpx.Client(timeout=20, follow_redirects=False) as client:
                response = client.get(f'https://restapi.amap.com/{ENDPOINTS[mode]}', params=params)
                response.raise_for_status()
                raw = response.json()
        except Exception:
            # Never expose credential-bearing URLs or upstream request dumps.
            raise AMapMCPError('高德道路路线服务暂时不可用，请稍后重试') from None
        if str(raw.get('infocode')) in {'10004', '10014', '10019', '10020', '10021'} and attempt < 2:
            time.sleep(attempt + 1)
            continue
        if str(raw.get('status', '1')) != '1' or str(raw.get('errcode', '0')) != '0':
            raise AMapMCPError('高德道路路线查询失败，请检查 Web 服务 Key 权限或配额')
        result = AMapMCPProvider()._route(raw, mode)
        if not result.get('geometry_available'):
            raise AMapMCPError('高德未返回该路段的道路坐标')
        result.update(provider='amap_web_service', source='amap_web_service', coordinate_system='GCJ02')
        logger.info('AMap road geometry completed mode=%s', mode)
        return result
    raise AMapMCPError('高德道路路线请求频率超限')
