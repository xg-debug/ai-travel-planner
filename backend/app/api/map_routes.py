from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.domain import travel_domain_service
from app.domain.travel_domain import MapExportValidationError
from app.mcp_tools.amap_provider import AMapMCPError
from app.services.map_route_service import plan_day_map_route

router = APIRouter()

class MapPoint(BaseModel):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    title: str = Field(default='', max_length=200)
    poiId: str = Field(default='', max_length=100)

class MapSegment(BaseModel):
    dayIndex: int = Field(default=0, ge=0, le=30)
    title: str = Field(default='', max_length=200)
    points: list[MapPoint] = Field(default_factory=list, max_length=20)

class MapRouteRequest(BaseModel):
    mode: Literal['touring', 'walking', 'driving', 'bicycling', 'transit'] = 'touring'
    city: str = Field(default='', max_length=100)
    cityd: str = Field(default='', max_length=100)
    segments: list[MapSegment] = Field(default_factory=list, max_length=14)

@router.post('/route/map')
@router.post('/route/tencent', deprecated=True)
def calculate_map_trip_routes(request: MapRouteRequest):
    if request.mode == 'transit' and not request.city:
        raise HTTPException(422, '公交路线需要提供城市')
    return {'mode': request.mode, 'segments': [
        {'dayIndex': segment.dayIndex, **plan_day_map_route([p.model_dump() for p in segment.points], request.mode, request.city, request.cityd)}
        for segment in request.segments if len(segment.points) >= 2
    ]}

class AroundRequest(BaseModel):
    point: MapPoint
    keyword: str = Field(default='餐厅', min_length=1, max_length=100)
    radius: int = Field(default=1500, ge=100, le=50000)

@router.post('/map/around')
def search_around(request: AroundRequest):
    try:
        return {'pois': travel_domain_service.search_around(f'{request.point.longitude},{request.point.latitude}', request.keyword, request.radius)}
    except AMapMCPError as exc:
        raise HTTPException(503, str(exc)) from None

@router.get('/map/pois/{poi_id}')
def poi_detail(poi_id: str):
    if not poi_id or len(poi_id) > 100:
        raise HTTPException(422, '无效的地点 ID')
    try:
        return travel_domain_service.poi_detail(poi_id)
    except AMapMCPError as exc:
        raise HTTPException(503, str(exc)) from None

class MapExportRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    segments: list[MapSegment] = Field(min_length=1, max_length=14)

@router.post('/map/export')
def export_personal_map(request: MapExportRequest):
    days = [{'title': segment.title or f'第 {segment.dayIndex + 1} 天', 'pointInfoList': [
        {'name': p.title or '行程地点', 'lon': p.longitude, 'lat': p.latitude, 'poiId': p.poiId}
        for p in segment.points
    ]} for segment in request.segments if segment.points]
    if not days:
        raise HTTPException(422, '行程没有可导出的坐标点位')
    try:
        return travel_domain_service.export_map(request.title, days)
    except MapExportValidationError as exc:
        raise HTTPException(422, str(exc)) from None
    except AMapMCPError as exc:
        raise HTTPException(503, str(exc)) from None
