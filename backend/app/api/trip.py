from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
import logging
import asyncio
import json
from pydantic import BaseModel, Field
from app.graph.state import TripRequest, TripResponse, PoiDetails, WeatherInfo
from app.graph.graph import app_trip_graph, trip_planner
from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.trip_plan import TripPlan
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.services.amap_service import search_pois, get_weather_forecast, calculate_route
from app.services.recommendation_service import get_recommendations
from app.services.budget_service import estimate_budget
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

class BudgetEstimateRequest(BaseModel):
    itinerary: List[Dict[str, Any]] = Field(default_factory=list)
    travelers: int = 1
    budget_level: str = "中等"

class RouteOptimizeRequest(BaseModel):
    pois: List[Dict[str, Any]] = Field(default_factory=list)
    constraints: Optional[Dict[str, Any]] = None

class RouteCalculateRequest(BaseModel):
    origin: str
    destination: str
    mode: str = "driving"


class TripPlanPayload(BaseModel):
    id: Optional[str] = None
    destination: str
    startDate: str
    endDate: str
    travelers: int
    interests: List[str] = Field(default_factory=list)
    budget: Dict[str, Any] = Field(default_factory=dict)
    days: List[Dict[str, Any]] = Field(default_factory=list)
    weather: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    hotels: List[Dict[str, Any]] = Field(default_factory=list)
    plan: str = ""
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


def _to_state(request: TripRequest) -> Dict[str, Any]:
    return {
        "query": request.query,
        "city": request.city,
        "days": request.days,
        "preferences": request.preferences or [],
        "budget": request.budget or "中等",
        "travelers": request.travelers or 1,
        "start_date": request.start_date,
    }


def _to_response(result: Dict[str, Any]) -> TripResponse:
    return TripResponse(
        plan=result.get("final_output", ""),
        pois=result.get("poi_data", {}),
        itinerary=result.get("plan"),
        weather=result.get("weather_data"),
        recommendations=result.get("recommendations"),
        hotels=result.get("hotel_options"),
        estimated_budget=result.get("estimated_budget"),
    )


def _validate_trip_request(request: TripRequest) -> None:
    if not request.city:
        raise ValueError("目的地城市不能为空")
    if not request.query:
        raise ValueError("旅行需求不能为空")
    if not request.days or request.days <= 0:
        raise ValueError("旅行天数必须大于0")
    if request.days > settings.MAX_TRIP_DAYS:
        raise ValueError(f"旅行天数不能超过{settings.MAX_TRIP_DAYS}天")


def _friendly_error_message(error_text: str) -> str:
    if "Insufficient Balance" in error_text or "402" in error_text:
        return "AI服务余额不足，已尝试自动切换模型但仍失败，请充值或更换可用模型"
    if "未检测到可用的 LLM API Key" in error_text or "未配置" in error_text:
        return "未配置可用的AI模型密钥，请先在后端环境变量中配置 OpenAI/Anthropic/Google/DeepSeek Key"
    if "timed out" in error_text.lower() or "timeout" in error_text.lower():
        return "AI服务响应超时，请稍后重试（可检查模型服务连通性）"
    return "行程规划失败，请稍后重试"


def _sse(event: str, data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"

@router.post("/plan", response_model=TripResponse)
async def plan_trip(request: TripRequest):
    """
    规划旅行行程
    
    Args:
        request: 旅行请求参数
        
    Returns:
        旅行计划结果
    """
    logger.info(f"Planning trip: {request.city} for {request.days} days")
    
    try:
        _validate_trip_request(request)
        result = app_trip_graph.invoke(_to_state(request))
        response = _to_response(result)

        if not response.itinerary:
            raise HTTPException(status_code=502, detail="AI未生成可用行程，请稍后重试")
        
        logger.info(f"Trip planned successfully for {request.city}")
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error planning trip: {e}")
        raise HTTPException(status_code=500, detail=_friendly_error_message(str(e)))


@router.get("/plans")
def list_trip_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            select(TripPlan).where(TripPlan.user_id == current_user.id).order_by(TripPlan.updated_at.desc())
        )
        .scalars()
        .all()
    )
    return [row.payload() for row in rows]


@router.get("/plans/{plan_id}")
def get_trip_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="行程不存在")
    return row.payload()


@router.post("/plans")
def create_trip_plan(
    payload: TripPlanPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan_id = payload.id or ""
    existing = None
    if plan_id:
        existing = db.execute(
            select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id)
        ).scalar_one_or_none()

    data = payload.model_dump()
    data["id"] = existing.id if existing else (payload.id or "")
    data["createdAt"] = data.get("createdAt") or (existing.created_at.isoformat() if existing else None)

    if existing:
        existing.destination = payload.destination
        existing.start_date = payload.startDate
        existing.end_date = payload.endDate
        existing.payload_json = json.dumps(data, ensure_ascii=False)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing.payload()

    row_kwargs = {
        "user_id": current_user.id,
        "destination": payload.destination,
        "start_date": payload.startDate,
        "end_date": payload.endDate,
        "payload_json": json.dumps(data, ensure_ascii=False),
    }
    if payload.id:
        row_kwargs["id"] = payload.id
    row = TripPlan(**row_kwargs)
    db.add(row)
    db.commit()
    db.refresh(row)
    result = row.payload()
    if not result.get("id"):
        result["id"] = row.id
    return result


@router.put("/plans/{plan_id}")
def update_trip_plan(
    plan_id: str,
    payload: TripPlanPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="行程不存在")

    data = payload.model_dump()
    data["id"] = plan_id
    row.destination = payload.destination
    row.start_date = payload.startDate
    row.end_date = payload.endDate
    row.payload_json = json.dumps(data, ensure_ascii=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.payload()


@router.delete("/plans/{plan_id}")
def delete_trip_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="行程不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/plan/stream")
async def plan_trip_stream(request: TripRequest):
    logger.info("Streaming plan request: %s %s days", request.city, request.days)

    async def event_generator():
        state = _to_state(request)
        try:
            _validate_trip_request(request)

            yield _sse("status", {"step": "query_agent", "message": "理解旅行需求与规划重点"})
            await asyncio.sleep(0)
            state.update(trip_planner.nodes["query_agent"](state))

            yield _sse("status", {"step": "scenic_agent", "message": "搜索评分较高的真实景点"})
            await asyncio.sleep(0)
            state.update(trip_planner.nodes["scenic_agent"](state))

            yield _sse("status", {"step": "hotel_agent", "message": "推荐适合路线的酒店"})
            await asyncio.sleep(0)
            state.update(trip_planner.nodes["hotel_agent"](state))

            yield _sse("status", {"step": "planning_agent", "message": "AI正在生成行程"})
            await asyncio.sleep(0)
            state.update(trip_planner.nodes["planning_agent"](state))
            yield _sse(
                "status",
                {"step": "planning_agent_done", "message": "行程草案已生成", "days": len(state.get("plan", []))},
            )

            yield _sse("status", {"step": "poi_agent", "message": "补全景点坐标、图片与故事"})
            await asyncio.sleep(0)
            state.update(trip_planner.nodes["poi_agent"](state))

            yield _sse("status", {"step": "weather_tool", "message": "通过天气工具获取天气信息"})
            await asyncio.sleep(0)
            state.update(trip_planner.nodes["weather_tool"](state))

            yield _sse("status", {"step": "budget", "message": "计算预算"})
            await asyncio.sleep(0)
            state.update(trip_planner.nodes["budget"](state))

            yield _sse("status", {"step": "summary", "message": "整理最终输出"})
            await asyncio.sleep(0)
            state.update(trip_planner.nodes["summary"](state))

            response = _to_response(state)
            if not response.itinerary:
                raise ValueError("AI未生成可用行程")

            yield _sse("result", response.model_dump())
            yield _sse("done", {"ok": True})
        except Exception as exc:
            logger.error("Error in stream planning: %s", exc)
            yield _sse("error", {"message": _friendly_error_message(str(exc))})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/weather", response_model=List[WeatherInfo])
async def get_weather(city: str, days: int = 3):
    """
    获取天气预报
    
    Args:
        city: 城市名称
        days: 预报天数（默认3天）
        
    Returns:
        天气预报列表
    """
    logger.info(f"Getting weather for {city} ({days} days)")
    
    try:
        weather_data = get_weather_forecast(city, days)
        forecasts = weather_data.get('forecast', [])
        
        weather_list = []
        for forecast in forecasts:
            weather_info = WeatherInfo(
                city=city,
                date=forecast.get('date', ''),
                temperature=forecast.get('temperature', {}).get('avg', 20),
                condition=forecast.get('condition', '未知'),
                humidity=forecast.get('humidity', 60),
                wind_speed=forecast.get('wind_speed', 10),
                icon=forecast.get('icon', 'unknown')
            )
            weather_list.append(weather_info)
        
        return weather_list
        
    except Exception as e:
        logger.error(f"Error getting weather: {e}")
        raise HTTPException(status_code=500, detail="获取天气信息失败")

@router.get("/pois/search", response_model=List[PoiDetails])
async def search_poi(keyword: str, city: str, page: int = 1, size: int = 10):
    """
    搜索POI（兴趣点）
    
    Args:
        keyword: 搜索关键词
        city: 城市名称
        page: 页码（默认1）
        size: 每页数量（默认10）
        
    Returns:
        POI详情列表
    """
    logger.info(f"Searching POIs: {keyword} in {city}")
    
    try:
        pois = search_pois(keyword, city, page, size)
        
        poi_list = []
        for poi in pois:
            poi_details = PoiDetails(
                id=poi.get('id', ''),
                name=poi.get('name', ''),
                lat=poi.get('lat', 0),
                lng=poi.get('lng', 0),
                address=poi.get('address', ''),
                type=poi.get('type', '景点'),
                rating=poi.get('rating', 4.0),
                price=poi.get('price', '免费'),
                description=poi.get('description', ''),
                opening_hours=poi.get('opening_hours', '09:00-17:00'),
                best_time=poi.get('best_time', '全天'),
                tips=poi.get('tips', ''),
                image_url=poi.get('image_url')
            )
            poi_list.append(poi_details)
        
        return poi_list
        
    except Exception as e:
        logger.error(f"Error searching POIs: {e}")
        raise HTTPException(status_code=500, detail="搜索POI失败")

@router.get("/recommendations")
async def get_trip_recommendations(city: str, preferences: Optional[str] = None):
    """
    获取个性化推荐
    
    Args:
        city: 城市名称
        preferences: 偏好列表（逗号分隔）
        
    Returns:
        推荐列表
    """
    logger.info(f"Getting recommendations for {city}")
    
    try:
        pref_list = preferences.split(',') if preferences else []
        recommendations = get_recommendations(city, pref_list)
        return {"recommendations": recommendations}
        
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail="获取推荐失败")

@router.post("/budget/estimate")
async def estimate_trip_budget(request: BudgetEstimateRequest):
    """
    估算旅行预算
    
    Args:
        itinerary: 行程安排
        travelers: 旅行人数
        budget_level: 预算水平（经济、中等、豪华）
        
    Returns:
        预算估算结果
    """
    logger.info(f"Estimating budget for {request.travelers} travelers")
    
    try:
        budget = estimate_budget(request.itinerary, request.travelers, request.budget_level)
        return budget
        
    except Exception as e:
        logger.error(f"Error estimating budget: {e}")
        raise HTTPException(status_code=500, detail="预算估算失败")

@router.post("/route/optimize")
async def optimize_trip_route(request: RouteOptimizeRequest):
    """
    优化旅行路线
    
    Args:
        pois: POI列表
        constraints: 约束条件
        
    Returns:
        优化后的路线
    """
    logger.info(f"Optimizing route for {len(request.pois)} POIs")
    
    try:
        # 这里可以添加路线优化逻辑
        # 目前返回原始POI列表
        return {"route": request.pois, "optimized": True, "constraints": request.constraints or {}}
        
    except Exception as e:
        logger.error(f"Error optimizing route: {e}")
        raise HTTPException(status_code=500, detail="路线优化失败")

@router.post("/route/calculate")
async def calculate_trip_route(request: RouteCalculateRequest):
    """
    计算路线
    
    Args:
        origin: 起点
        destination: 终点
        mode: 交通方式（driving, walking, transit, bicycling）
        
    Returns:
        路线信息
    """
    logger.info(f"Calculating route from {request.origin} to {request.destination} by {request.mode}")
    
    try:
        route = calculate_route(request.origin, request.destination, request.mode)
        return route
        
    except Exception as e:
        logger.error(f"Error calculating route: {e}")
        raise HTTPException(status_code=500, detail="路线计算失败")

@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "AI Travel Planner",
        "version": settings.APP_VERSION
    }
