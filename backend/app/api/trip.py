from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, date
from pydantic import BaseModel, Field
from app.graph.state import TripRequest, TripResponse, PoiDetails, WeatherInfo
from app.graph.graph import app_trip_graph
from app.services.amap_service import search_pois, get_weather_forecast, calculate_route
from app.services.recommendation_service import get_recommendations
from app.services.budget_service import estimate_budget, optimize_budget
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
        # 准备状态数据
        state = {
            "query": request.query,
            "city": request.city,
            "days": request.days,
            "preferences": request.preferences or [],
            "budget": request.budget or "中等",
            "travelers": request.travelers or 1,
            "start_date": request.start_date
        }
        
        # 执行行程规划
        result = app_trip_graph.invoke(state)
        
        # 构建响应
        response = TripResponse(
            plan=result.get('final_output', ''),
            pois=result.get('poi_data', {}),
            itinerary=result.get('plan'),
            weather=result.get('weather_data'),
            recommendations=result.get('recommendations'),
            estimated_budget=result.get('estimated_budget')
        )
        
        logger.info(f"Trip planned successfully for {request.city}")
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error planning trip: {e}")
        raise HTTPException(status_code=500, detail="行程规划失败，请稍后重试")

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
                tips=poi.get('tips', '')
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
