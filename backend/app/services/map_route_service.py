"""One cached route pipeline shared by planning, web and mini-program maps."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from app.domain import travel_domain_service

MODES = {'walking', 'driving', 'bicycling', 'transit', 'touring'}


def plan_day_map_route(points: list[dict[str, Any]], mode: str, city: str = '', cityd: str = '') -> dict:
    if mode not in MODES:
        raise ValueError('不支持的交通方式')
    pairs = list(zip(points, points[1:]))
    def plan(pair):
        origin, destination = pair
        selected = 'walking' if mode == 'touring' else mode
        # Touring is a deterministic choice. Explicit modes never silently change.
        if mode == 'touring':
            from math import cos, hypot, radians
            km = hypot((destination['longitude'] - origin['longitude']) * cos(radians(origin['latitude'])) * 111,
                       (destination['latitude'] - origin['latitude']) * 111)
            selected = 'walking' if km <= 3.5 else 'driving'
        try:
            result = travel_domain_service.calculate_route(
                f"{origin['longitude']},{origin['latitude']}", f"{destination['longitude']},{destination['latitude']}",
                selected, city=city if selected == 'transit' else '', cityd=(cityd or city) if selected == 'transit' else '',
            )
            return {**result, 'mode': selected, 'provider': result.get('provider') or result.get('source') or 'amap_mcp', 'ok': True}
        except Exception:
            return {'distance': 0, 'duration': 0, 'polyline': [], 'polylines': [], 'instructions': [],
                    'provider': 'unavailable', 'mode': selected, 'ok': False,
                    'error': '该路段暂未获取到路线，请稍后重试或选择其他交通方式'}
    if pairs:
        with ThreadPoolExecutor(max_workers=3) as pool:
            legs = list(pool.map(plan, pairs))
    else:
        legs = []
    for i, leg in enumerate(legs):
        leg.update(fromIndex=i, toIndex=i + 1)
    partial = any(not leg['ok'] for leg in legs)
    geometry = bool(legs) and all(leg.get('polylines') or leg.get('polyline') for leg in legs)
    return {'distance': sum(float(x.get('distance') or 0) for x in legs),
            'duration': sum(float(x.get('duration') or 0) for x in legs),
            'polyline': [], 'legs': legs, 'mode': mode, 'provider': ','.join(dict.fromkeys(x['provider'] for x in legs)) or 'none',
            'partial': partial, 'geometry_available': geometry,
            'warning': '部分路段暂未获取到路线。' if partial else ('' if geometry else '暂未取得道路折线，地图仅显示地点，可打开高德查看导航。')}


def enrich_itinerary_routes(state: dict) -> None:
    """Attach the same route data that the map endpoint will serve from cache."""
    for day in state.get('plan') or []:
        activities = [a for a in day.get('activities') or [] if (a.get('coordinates') or {}).get('lat') and (a.get('coordinates') or {}).get('lng') and not (a.get('isIntercityTransport') or a.get('is_intercity_transport'))]
        points = [{'latitude': a['coordinates']['lat'], 'longitude': a['coordinates']['lng']} for a in activities
                  if a['coordinates'].get('lat') and a['coordinates'].get('lng')]
        if len(points) < 2:
            continue
        mode = state.get('route_mode') or 'touring'
        route = plan_day_map_route(points, mode, city=state.get('city', ''))
        day['map_route'] = route
        for activity, leg in zip(activities[1:], route['legs']):
            if leg['ok']:
                activity['transport_route'] = leg
                label = {'walking': '步行', 'driving': '驾车', 'bicycling': '骑行', 'transit': '公交'}.get(leg['mode'], '交通')
                activity['transportation'] = f"{label}约 {round(float(leg.get('duration') or 0) / 60)} 分钟，{float(leg.get('distance') or 0) / 1000:.1f} 公里"
