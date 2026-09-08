"""Official AMap Streamable HTTP MCP adapter; no direct REST requests."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import threading
import time
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings
from app.mcp_tools.base import MCPToolProvider, run_async_sync
from app.mcp_tools.amap_payloads import AMapPayloads
from app.services.runtime_config import get_map_api_key, get_amap_mcp_url
from app.services.cache import cache_key, get_cache, set_cache

# MCP URLs carry credentials; never emit HTTPX's request URLs at INFO level.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp.client.streamable_http").setLevel(logging.CRITICAL)
logger = logging.getLogger(__name__)


class MCPRateLimiter:
    """Space tool calls across all sessions and event loops in this process."""

    def __init__(self):
        self._lock = threading.Lock()
        self._next_call = 0.0

    def reserve_delay(self) -> float:
        with self._lock:
            now = time.monotonic()
            scheduled = max(now, self._next_call)
            self._next_call = scheduled + 1 / max(settings.AMAP_MCP_MAX_QPS, 0.1)
            return scheduled - now

    async def wait(self):
        await asyncio.sleep(self.reserve_delay())


_rate_limiter = MCPRateLimiter()


class AMapMCPError(RuntimeError):
    pass


def mcp_connection() -> tuple[str, dict[str, str]]:
    parts = urlsplit(get_amap_mcp_url())
    if parts.scheme != "https" or parts.hostname != "mcp.amap.com" or parts.path.rstrip('/') != '/mcp':
        raise AMapMCPError("请配置高德官方 Streamable HTTP 地址 https://mcp.amap.com/mcp")
    query = dict(parse_qsl(parts.query))
    key = get_map_api_key("amap_mcp") or query.get("key")
    if not key:
        raise AMapMCPError("请配置高德 MCP Key（兼容 AMAP_API_KEY）")
    query['key'] = key
    headers = json.loads(settings.AMAP_MCP_HEADERS or '{}')
    if not isinstance(headers, dict):
        raise AMapMCPError("AMAP_MCP_HEADERS 必须是 JSON 对象")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), '')), headers


def coordinate(value: str) -> str:
    try:
        lng, lat = map(float, value.split(','))
        if not all(math.isfinite(n) for n in (lng, lat)) or not (-180 <= lng <= 180 and -90 <= lat <= 90):
            raise ValueError
        return f'{lng:.6f},{lat:.6f}'
    except (ValueError, TypeError, AttributeError):
        raise ValueError("请提供有效的经度、纬度坐标") from None


def safe_map_link(value: Any) -> str:
    strings = []
    def visit(item):
        if isinstance(item, str):
            strings.extend(re.findall(r'(?:https://|amapuri://|amap://)[^\s<>"\[\]]+', item))
        elif isinstance(item, dict):
            for child in item.values(): visit(child)
        elif isinstance(item, list):
            for child in item: visit(child)
    visit(value)
    for link in strings:
        link = link.rstrip(').,，。')
        parts = urlsplit(link)
        host = parts.hostname or ''
        if parts.scheme in {'amapuri', 'amap'} or (parts.scheme == 'https' and (host == 'amap.com' or host.endswith('.amap.com'))):
            return link
    raise AMapMCPError("高德未返回可用的专属地图链接，请稍后重试")


class AMapMCPProvider(AMapPayloads, MCPToolProvider):
    provider_name = 'amap_mcp'
    ROUTE_TOOLS = {
        'walking': 'maps_direction_walking', 'driving': 'maps_direction_driving',
        'bicycling': 'maps_direction_bicycling', 'transit': 'maps_direction_transit_integrated',
    }

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        try:
            return run_async_sync(asyncio.wait_for(self._dispatch(tool_name, arguments), timeout=settings.AMAP_MCP_REQUEST_TIMEOUT))
        except (AMapMCPError, ValueError):
            raise
        except Exception:
            # SDK exception groups may contain the full credential-bearing URL.
            raise AMapMCPError("高德 MCP 暂时不可用，请检查 Key、网络或服务配额后重试") from None

    async def _call(self, session, name, args):
        # Only retry reads. Never replay an export that may have created a map.
        attempts = 1 if name.startswith('maps_schema_') else 3
        for attempt in range(attempts):
            await _rate_limiter.wait()
            result = await session.call_tool(name, args)
            raw = getattr(result, 'structuredContent', None)
            if raw is None:
                raw = self._normalize_mcp_result(result.model_dump(by_alias=True, exclude_none=True))
            failed = result.isError or (isinstance(raw, dict) and (str(raw.get('status', '1')) == '0' or raw.get('error')))
            if not failed:
                logger.info('AMap MCP tool completed transport=streamable_http tool=%s', name)
                return raw
            error_text = json.dumps(raw, ensure_ascii=False).lower()
            limited = any(marker in error_text for marker in ('qps', 'too_many_requests', 'rate limit', 'access_too_frequent'))
            if limited and attempt + 1 < attempts:
                logger.info('AMap MCP rate limited tool=%s retry=%s', name, attempt + 1)
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            reason = '请求频率超限，请稍后重试' if limited else '调用失败，请检查参数或配额'
            raise AMapMCPError(f'高德 MCP 工具 {name} {reason}')

    async def _dispatch(self, tool, args):
        url, headers = mcp_connection()
        async with streamablehttp_client(url, headers=headers, timeout=settings.AMAP_MCP_CONNECT_TIMEOUT,
                                         sse_read_timeout=settings.AMAP_MCP_REQUEST_TIMEOUT) as (read, write, _):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=settings.AMAP_MCP_REQUEST_TIMEOUT)) as session:
                await session.initialize()
                if tool in {'geocode_pois', 'around_search'}:
                    size = max(1, min(int(args.get('size', 8)), 20))
                    if tool == 'geocode_pois':
                        payload = {'keywords': args['keyword'], 'city': args.get('city', ''), 'citylimit': bool(args.get('city'))}
                        raw = await self._call(session, 'maps_text_search', payload)
                    else:
                        raw = await self._call(session, 'maps_around_search', {
                            'keywords': args.get('keyword') or '餐厅', 'location': coordinate(args['location']),
                            'radius': str(max(100, min(int(args.get('radius', 1500)), 50000))),
                        })
                    items = self._extract_items(raw, ('pois', 'items', 'results', 'data'))
                    start = (max(1, int(args.get('page', 1))) - 1) * size
                    semaphore = asyncio.Semaphore(3)
                    async def enrich(item):
                        async with semaphore:
                            try:
                                detail = await self._detail(session, str(item.get('id') or ''))
                                return {**self._normalize_poi(item), **detail,
                                        'image_url': detail.get('image_url') or item.get('photo') or ''}
                            except AMapMCPError:
                                # Preserve real search evidence, without claiming it was verified.
                                return self._normalize_poi(item)
                    return await asyncio.gather(*(enrich(item) for item in items[start:start + size]))
                if tool == 'poi_detail':
                    return await self._detail(session, args['id'])
                if tool == 'get_weather_forecast':
                    raw = self._unwrap_payload(await self._call(session, 'maps_weather', {'city': args['city']}))
                    forecasts = raw.get('forecasts') or raw.get('forecast') or []
                    city, report = raw.get('city', args['city']), raw.get('reporttime', '')
                    if forecasts and 'casts' in forecasts[0]:
                        city, report = forecasts[0].get('city', city), forecasts[0].get('reporttime', report)
                        forecasts = forecasts[0]['casts']
                    if not forecasts:
                        raise AMapMCPError('高德暂未返回该城市天气预报')
                    return {'city': city, 'report_time': report,
                            'forecast': [self._normalize_forecast(x) for x in forecasts[:int(args.get('days', 3))]]}
                if tool == 'plan_route':
                    mode = args.get('mode', 'driving')
                    if mode not in self.ROUTE_TOOLS:
                        raise ValueError('不支持的交通方式')
                    payload = {'origin': coordinate(args['origin']), 'destination': coordinate(args['destination'])}
                    if mode == 'transit':
                        if not args.get('city') or not args.get('cityd'):
                            raise ValueError('公交路线需要起点城市和终点城市')
                        payload.update(city=args['city'], cityd=args['cityd'])
                    raw = await self._call(session, self.ROUTE_TOOLS[mode], payload)
                    return self._route(raw, mode)
                if tool == 'personal_map':
                    raw = await self._call(session, 'maps_schema_personal_map', args)
                    return {'url': safe_map_link(raw), 'provider': self.provider_name}
                raise ValueError(f'不支持的地图工具：{tool}')

    async def _detail(self, session, poi_id):
        if not poi_id:
            raise AMapMCPError('缺少高德 POI ID')
        ck = cache_key('amap_mcp_v1', 'detail', poi_id)
        cached = get_cache(ck)
        if cached is not None:
            return cached
        raw = await self._call(session, 'maps_search_detail', {'id': poi_id})
        items = self._extract_items(raw, ('pois', 'poi', 'data', 'result'))
        if not items:
            raise AMapMCPError('未找到对应的高德地点详情')
        item = items[0]
        returned_id = item.get('id') or item.get('poiid') or poi_id
        if returned_id != poi_id:
            raise AMapMCPError('高德地点详情 ID 不匹配')
        result = self._normalize_poi({**item, 'id': poi_id})
        result['verified'] = True
        set_cache(ck, result)
        return result

    def _normalize_poi(self, item, poi_type=None):
        result = super()._normalize_poi(item, poi_type)
        result.update(source=self.provider_name, verified=False)
        result['image_url'] = result.get('image_url') or item.get('photo') or ''
        # Official search often supplies typecode only; preserve usable categories.
        if result['type'].isdigit():
            result['type'] = {'05': '餐饮服务', '10': '住宿服务', '11': '风景名胜'}.get(result['type'][:2], result['type'])
        result.pop('raw', None)
        return result

    def _route(self, raw, mode):
        item = self._unwrap_payload(raw)
        item = item.get('route') or item
        choices = item.get('transits' if mode == 'transit' else 'paths') or []
        if not choices:
            raise AMapMCPError('高德未找到该交通方式的可用路线')
        path = choices[0]
        steps = path.get('segments' if mode == 'transit' else 'steps') or []
        instructions, lines = [], []
        def walk(value):
            if isinstance(value, dict):
                if value.get('instruction'): instructions.append(str(value['instruction']))
                if value.get('name') and ('departure_stop' in value or 'arrival_stop' in value):
                    instructions.append(f"乘坐{value['name']}：{value.get('departure_stop', {}).get('name', '')} → {value.get('arrival_stop', {}).get('name', '')}")
                if value.get('polyline'):
                    points = []
                    for pair in str(value['polyline']).split(';'):
                        try:
                            lng, lat = map(float, coordinate(pair).split(','))
                            points.append({'latitude': lat, 'longitude': lng})
                        except ValueError: continue
                    if len(points) >= 2: lines.append(points)
                for k, child in value.items():
                    if k != 'polyline': walk(child)
            elif isinstance(value, list):
                for child in value: walk(child)
        walk(steps)
        cost = path.get('cost') if isinstance(path.get('cost'), dict) else {}
        return {'distance': self._safe_float(path.get('distance') or item.get('distance')),
                'duration': self._safe_float(path.get('duration') or cost.get('duration')),
                'steps': steps, 'instructions': instructions, 'polylines': lines,
                'polyline': lines[0] if len(lines) == 1 else [], 'geometry_available': bool(lines),
                'mode': mode, 'source': self.provider_name, 'provider': self.provider_name,
                'toll': self._safe_float(path.get('tolls') or cost.get('tolls')),
                'traffic_lights': int(self._safe_float(path.get('traffic_lights')))}
