from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
import logging
import asyncio
import json
import threading
import time
import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from app.agents.orchestrator import llm_orchestrator_runner
from app.graph.state import TripRequest, TripResponse, PoiDetails, WeatherInfo
from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.trip_plan import TripPlan
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.domain import travel_domain_service
from app.services.recommendation_service import get_recommendations
from app.services.budget_service import estimate_budget
from app.services.amap_service import amap_service
from app.services.tencent_map_service import tencent_map_service
from app.services.runtime_config import get_map_api_key, is_present_secret
from app.core.config import settings
from app.services.travel_intent import normalize_trip_city_and_query
from app.agents.shared import dedupe_recommendations

logger = logging.getLogger(__name__)
router = APIRouter()

PLAN_JOB_TTL_SECONDS = 60 * 60
_plan_jobs: Dict[str, Dict[str, Any]] = {}
_plan_jobs_lock = threading.RLock()

PLAN_JOB_STEP_PROGRESS = {
    "planner_agent": 5,
    "weather_tool": 12,
    "attraction_agent": 22,
    "food_agent": 32,
    "hotel_agent": 42,
    "scoring": 52,
    "transport_agent": 60,
    "synthesizer_agent": 70,
    "synthesizer_agent_done": 78,
    "route_grounding": 82,
    "poi_agent": 86,
    "reviewer_agent": 90,
    "reflection_rerun": 92,
    "budget": 94,
    "risk_notice": 96,
    "summary": 98,
}

class BudgetEstimateRequest(BaseModel):
    itinerary: List[Dict[str, Any]] = Field(default_factory=list)
    travelers: int = 1
    budget_level: str = "中等"
    intercity_transport: Optional[Dict[str, Any]] = None

class RouteOptimizeRequest(BaseModel):
    pois: List[Dict[str, Any]] = Field(default_factory=list)
    constraints: Optional[Dict[str, Any]] = None

class RouteCalculateRequest(BaseModel):
    origin: str
    destination: str
    mode: str = "driving"


class TencentRoutePoint(BaseModel):
    latitude: float
    longitude: float
    title: Optional[str] = None


class TencentRouteSegmentRequest(BaseModel):
    dayIndex: int = 0
    points: List[TencentRoutePoint] = Field(default_factory=list)


class TencentRouteRequest(BaseModel):
    mode: str = "driving"
    segments: List[TencentRouteSegmentRequest] = Field(default_factory=list)


def _available_route_providers() -> List[str]:
    providers: List[str] = []
    if is_present_secret(get_map_api_key("tencent")):
        providers.append("tencent")
    if is_present_secret(get_map_api_key("amap")):
        providers.append("amap")
    return providers


def _fallback_polyline(origin: Dict[str, Any], destination: Dict[str, Any]) -> List[Dict[str, float]]:
    return [
        {
            "latitude": float(origin.get("latitude") or origin.get("lat") or 0),
            "longitude": float(origin.get("longitude") or origin.get("lng") or origin.get("lon") or 0),
        },
        {
            "latitude": float(destination.get("latitude") or destination.get("lat") or 0),
            "longitude": float(destination.get("longitude") or destination.get("lng") or destination.get("lon") or 0),
        },
    ]


def _merge_polyline(target: List[Dict[str, float]], source: List[Dict[str, float]]) -> None:
    if not source:
        return
    if target:
        target.extend(source[1:])
    else:
        target.extend(source)


def _format_amap_point(point: Dict[str, Any]) -> str:
    latitude = float(point.get("latitude") or point.get("lat") or 0)
    longitude = float(point.get("longitude") or point.get("lng") or point.get("lon") or 0)
    return f"{longitude},{latitude}"


def _parse_amap_step_polyline(steps: List[Dict[str, Any]]) -> List[Dict[str, float]]:
    points: List[Dict[str, float]] = []
    for step in steps or []:
        for pair in str(step.get("polyline", "") or "").split(";"):
            values = pair.split(",")
            if len(values) < 2:
                continue
            try:
                points.append({"latitude": float(values[1]), "longitude": float(values[0])})
            except ValueError:
                continue
    return points


def _plan_amap_segment(origin: Dict[str, Any], destination: Dict[str, Any], mode: str) -> Dict[str, Any]:
    route_mode = mode if mode in {"driving", "walking", "bicycling", "transit"} else "driving"
    route = amap_service.calculate_route(_format_amap_point(origin), _format_amap_point(destination), route_mode)
    polyline = _parse_amap_step_polyline(route.get("steps", []) or [])
    if len(polyline) < 2:
        polyline = _fallback_polyline(origin, destination)
    return {
        "distance": int(route.get("distance", 0) or 0),
        "duration": int(route.get("duration", 0) or 0),
        "polyline": polyline,
        "provider": "amap",
    }


def _plan_tencent_segment(origin: Dict[str, Any], destination: Dict[str, Any], mode: str) -> Dict[str, Any]:
    route = tencent_map_service.plan_segment(origin, destination, mode)
    polyline = route.get("polyline", []) or _fallback_polyline(origin, destination)
    return {
        "distance": int(route.get("distance", 0) or 0),
        "duration": int(route.get("duration", 0) or 0),
        "polyline": polyline,
        "provider": "tencent",
    }


def _plan_route_segment(origin: Dict[str, Any], destination: Dict[str, Any], mode: str, providers: List[str]) -> Dict[str, Any]:
    errors: List[str] = []
    for provider in providers:
        try:
            if provider == "tencent":
                return _plan_tencent_segment(origin, destination, mode)
            if provider == "amap":
                return _plan_amap_segment(origin, destination, mode)
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
            logger.info("Route provider skipped provider=%s error=%s", provider, exc)
    return {
        "distance": 0,
        "duration": 0,
        "polyline": _fallback_polyline(origin, destination),
        "provider": "fallback",
        "error": " | ".join(errors) if errors else "未配置可用地图路线规划 Key，已使用坐标直线兜底",
    }


def _plan_day_map_route(points: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
    if len(points) < 2:
        return {"distance": 0, "duration": 0, "polyline": [], "legs": [], "provider": "none"}

    providers = _available_route_providers()
    if not providers:
        logger.warning("No map route provider configured, fallback to straight point polylines")

    legs: List[Dict[str, Any]] = []
    merged_polyline: List[Dict[str, float]] = []
    total_distance = 0
    total_duration = 0
    used_providers: List[str] = []

    for index in range(len(points) - 1):
        leg = _plan_route_segment(points[index], points[index + 1], mode, providers)
        leg["fromIndex"] = index
        leg["toIndex"] = index + 1
        legs.append(leg)
        total_distance += int(leg.get("distance", 0) or 0)
        total_duration += int(leg.get("duration", 0) or 0)
        provider = str(leg.get("provider") or "")
        if provider and provider not in used_providers:
            used_providers.append(provider)
        _merge_polyline(merged_polyline, leg.get("polyline", []) or [])

    return {
        "distance": total_distance,
        "duration": total_duration,
        "polyline": merged_polyline,
        "legs": legs,
        "provider": ",".join(used_providers) or "fallback",
    }


class TripPlanPayload(BaseModel):
    id: Optional[str] = None
    departureCity: Optional[str] = None
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
    intercityTransport: Dict[str, Any] = Field(default_factory=dict)
    plan: str = ""
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None

    def to_storage_dict(self, *, plan_id: Optional[str] = None, created_at: Optional[str] = None) -> Dict[str, Any]:
        data = self.model_dump()
        if plan_id:
            data["id"] = plan_id
        if created_at:
            data["createdAt"] = created_at
        return data


def _to_state(request: TripRequest) -> Dict[str, Any]:
    normalized = normalize_trip_city_and_query(request.city, request.query)
    return {
        "query": normalized["query"],
        "city": normalized["city"],
        "departure_city": (request.departure_city or "").strip(),
        "days": request.days,
        "preferences": request.preferences or [],
        "budget": request.budget or "中等",
        "budget_amount": request.budget_amount or 0,
        "travelers": request.travelers or 1,
        "start_date": request.start_date,
        "outbound_departure_datetime": request.outbound_departure_datetime,
        "return_arrival_datetime": request.return_arrival_datetime,
    }


def _to_response(result: Dict[str, Any]) -> TripResponse:
    return TripResponse(
        plan=result.get("final_output", ""),
        pois=result.get("poi_data", {}),
        itinerary=result.get("plan"),
        weather=result.get("weather_data"),
        recommendations=dedupe_recommendations(result.get("recommendations") or [], result.get("city", "")),
        hotels=result.get("hotel_options"),
        estimated_budget=result.get("estimated_budget"),
        daily_budgets=result.get("daily_budgets"),
        risk_notices=result.get("risk_notices"),
        weather_impacts=result.get("weather_impacts"),
        quality_score=result.get("quality_score"),
        intercity_transport=result.get("intercity_transport") or (result.get("transport_plan") or {}).get("intercity_transport"),
    )


def _cleanup_plan_jobs() -> None:
    now = time.time()
    with _plan_jobs_lock:
        expired = [
            job_id
            for job_id, job in _plan_jobs.items()
            if now - float(job.get("updated_at", job.get("created_at", now)) or now) > PLAN_JOB_TTL_SECONDS
        ]
        for job_id in expired:
            _plan_jobs.pop(job_id, None)


def _update_plan_job(job_id: str, **changes: Any) -> None:
    with _plan_jobs_lock:
        job = dict(_plan_jobs.get(job_id, {}))
        job.update(changes)
        job["updated_at"] = time.time()
        _plan_jobs[job_id] = job


def _update_plan_job_status(job_id: str, payload: Dict[str, Any]) -> None:
    step = str(payload.get("step") or "").strip()
    message = str(payload.get("message") or "").strip()
    if not step and not message:
        return
    logger.info("Plan job progress job_id=%s step=%s message=%s", job_id, step, message)
    changes: Dict[str, Any] = {
        "step": step,
        "message": message,
        "progress": PLAN_JOB_STEP_PROGRESS.get(step, 0),
    }
    _update_plan_job(job_id, **changes)


def _run_plan_job(job_id: str, state: Dict[str, Any]) -> None:
    logger.info("Plan job started job_id=%s city=%s days=%s", job_id, state.get("city"), state.get("days"))
    try:
        result: Dict[str, Any] = {}
        for event in llm_orchestrator_runner.stream(state):
            event_name = event.get("event")
            data = event.get("data") or {}
            if event_name == "status":
                _update_plan_job_status(job_id, data)
                continue
            if event_name == "result":
                result = dict(data.get("state", {}) or {})
        if not result:
            raise RuntimeError("LLM 主控智能体未生成最终行程")
        response = _to_response(result)
        if not response.itinerary:
            raise RuntimeError("AI未生成可用行程，请稍后重试")
        _update_plan_job(
            job_id,
            status="completed",
            step="summary",
            message="行程规划已完成",
            progress=100,
            result=response.model_dump(),
            error="",
        )
        logger.info("Plan job completed job_id=%s city=%s", job_id, state.get("city"))
    except Exception as exc:
        logger.exception("Plan job failed job_id=%s error=%s", job_id, exc)
        _update_plan_job(
            job_id,
            status="failed",
            progress=0,
            error=_friendly_error_message(str(exc)),
            raw_error=str(exc),
        )


def _parse_request_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError("出发和返程时间格式必须为 YYYY-MM-DD HH:MM")


def _validate_trip_state(state: Dict[str, Any]) -> None:
    if not state.get("city"):
        raise ValueError("目的地城市不能为空")
    if not state.get("query"):
        raise ValueError("旅行需求不能为空")
    days = int(state.get("days") or 0)
    if days <= 0:
        raise ValueError("旅行天数必须大于0")
    if days > settings.MAX_TRIP_DAYS:
        raise ValueError(f"旅行天数不能超过{settings.MAX_TRIP_DAYS}天")
    outbound_departure = _parse_request_datetime(state.get("outbound_departure_datetime"))
    return_arrival = _parse_request_datetime(state.get("return_arrival_datetime"))
    if outbound_departure and return_arrival and return_arrival <= outbound_departure:
        raise ValueError("返程到达时间必须晚于去程出发时间")


def _friendly_error_message(error_text: str) -> str:
    lower = error_text.lower()
    if "Insufficient Balance" in error_text or "402" in error_text:
        return "AI服务余额不足，请充值或更换可用模型"
    if (
        "invalid_api_key" in lower
        or "api key not valid" in lower
        or "invalid x-api-key" in lower
        or "incorrect api key" in lower
        or "authentication_error" in lower
    ):
        return "AI模型密钥无效，请在后端环境变量或管理后台中配置至少一个真实可用的 OpenAI/Anthropic/Google/DeepSeek Key，并移除占位 key"
    if "未检测到可用的 LLM API Key" in error_text or "未配置" in error_text:
        return "未配置可用的AI模型密钥，请先在后端环境变量中配置 OpenAI/Anthropic/Google/DeepSeek Key"
    if "所有模型调用失败" in error_text:
        return "所有AI模型调用均失败，请检查默认模型服务是否可访问、API Key 是否有效，或增大 LLM_REQUEST_TIMEOUT_SECONDS 后重试"
    if "timed out" in lower or "timeout" in lower:
        return "AI服务响应超时，请稍后重试（可检查模型服务连通性）"
    if "真实景点候选不足" in error_text:
        return "未查询到足够的真实景点数据，请换一个更具体的城市或稍后重试"
    if "真实餐饮候选不足" in error_text:
        return "未查询到足够的真实餐饮数据，请换一个更具体的城市或稍后重试"
    if "真实酒店候选为空" in error_text:
        return "未查询到真实酒店数据，请检查酒店MCP或地图服务配置后重试"
    return "行程规划失败，请稍后重试"


def _sse(event: str, data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
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
    state = _to_state(request)
    logger.info("Planning trip: %s for %s days", state["city"], state["days"])
    
    try:
        _validate_trip_state(state)
        result = llm_orchestrator_runner.run(state)
        response = _to_response(result)

        if not response.itinerary:
            raise HTTPException(status_code=502, detail="AI未生成可用行程，请稍后重试")
        
        logger.info(f"Trip planned successfully for {request.city}")
        return response
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error planning trip: %s", e)
        raise HTTPException(status_code=500, detail=_friendly_error_message(str(e)))


@router.post("/plan/jobs")
async def start_plan_job(request: TripRequest, background_tasks: BackgroundTasks):
    """
    启动异步行程规划任务。

    小程序端长时间等待同步 /plan 容易触发 request 超时，因此使用短请求启动任务，再轮询结果。
    """
    state = _to_state(request)
    logger.info("Starting plan job: %s for %s days", state["city"], state["days"])
    try:
        _validate_trip_state(state)
    except ValueError as exc:
        logger.error("Validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    _cleanup_plan_jobs()
    job_id = uuid.uuid4().hex
    now = time.time()
    with _plan_jobs_lock:
        _plan_jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "city": state.get("city", ""),
            "days": state.get("days", 0),
            "step": "planner_agent",
            "message": "规划任务已启动",
            "progress": PLAN_JOB_STEP_PROGRESS["planner_agent"],
            "created_at": now,
            "updated_at": now,
            "result": None,
            "error": "",
        }
    background_tasks.add_task(_run_plan_job, job_id, state)
    return {"job_id": job_id, "status": "running"}


@router.get("/plan/jobs/{job_id}")
async def get_plan_job(job_id: str):
    _cleanup_plan_jobs()
    with _plan_jobs_lock:
        job = _plan_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="规划任务不存在或已过期")
        return {
            "job_id": job.get("job_id", job_id),
            "status": job.get("status", "running"),
            "city": job.get("city", ""),
            "days": job.get("days", 0),
            "step": job.get("step", ""),
            "message": job.get("message", ""),
            "progress": job.get("progress", 0),
            "result": job.get("result"),
            "error": job.get("error", ""),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
        }


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
    try:
        plan_id = payload.id or ""
        existing = None
        if plan_id:
            existing = db.execute(
                select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id)
            ).scalar_one_or_none()

        data = payload.to_storage_dict(
            plan_id=existing.id if existing else (payload.id or None),
            created_at=(existing.created_at.isoformat() if existing else None),
        )

        if existing:
            existing.sync_from_payload(data)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing.payload()

        row = TripPlan(
            user_id=current_user.id,
            destination=payload.destination,
            start_date=payload.startDate,
            end_date=payload.endDate,
        )
        if payload.id:
            row.id = payload.id
        row.sync_from_payload(data)
        db.add(row)
        db.commit()
        db.refresh(row)
        result = row.payload()
        if not result.get("id"):
            result["id"] = row.id
        return result
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Error saving trip plan: %s", exc)
        raise HTTPException(status_code=500, detail="保存行程失败，请稍后重试")


@router.put("/plans/{plan_id}")
def update_trip_plan(
    plan_id: str,
    payload: TripPlanPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        row = db.execute(
            select(TripPlan).where(TripPlan.id == plan_id, TripPlan.user_id == current_user.id)
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="行程不存在")

        data = payload.to_storage_dict(
            plan_id=plan_id,
            created_at=(row.payload().get("createdAt") or row.created_at.isoformat()),
        )
        row.sync_from_payload(data)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.payload()
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Error updating trip plan: %s", exc)
        raise HTTPException(status_code=500, detail="更新行程失败，请稍后重试")


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
    state = _to_state(request)
    logger.info("Streaming plan request: %s %s days", state["city"], state["days"])

    async def event_generator():
        try:
            _validate_trip_state(state)
            final_state = None
            for event in llm_orchestrator_runner.stream(state):
                await asyncio.sleep(0)
                if event["event"] == "status":
                    yield _sse("status", event["data"])
                    continue
                if event["event"] == "result":
                    final_state = event["data"]["state"]

            response = _to_response(final_state or {})
            if not response.itinerary:
                raise ValueError("AI未生成可用行程")

            yield _sse("result", response.model_dump())
            yield _sse("done", {"ok": True})
        except Exception as exc:
            logger.exception("Error in stream planning: %s", exc)
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
        weather_data = travel_domain_service.get_weather(city, days)
        forecasts = weather_data.get('forecast', [])
        
        weather_list = []
        for forecast in forecasts:
            weather_info = WeatherInfo(
                city=city,
                date=forecast.get('date', ''),
                temperature=forecast.get('temperature', {}).get('avg', 0),
                condition=forecast.get('condition', ''),
                day_condition=forecast.get('day_condition'),
                night_condition=forecast.get('night_condition'),
                humidity=forecast.get('humidity', 0),
                wind_speed=forecast.get('wind_speed', 0),
                day_wind_direction=forecast.get('day_wind_direction'),
                night_wind_direction=forecast.get('night_wind_direction'),
                day_wind_power=forecast.get('day_wind_power'),
                night_wind_power=forecast.get('night_wind_power'),
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
        pois = travel_domain_service.search_pois(keyword, city, page, size)
        
        poi_list = []
        for poi in pois:
            poi_details = PoiDetails(
                id=poi.get('id', ''),
                name=poi.get('name', ''),
                lat=poi.get('lat', 0),
                lng=poi.get('lng', 0),
                address=poi.get('address', ''),
                type=poi.get('type', ''),
                rating=poi.get('rating', 0.0),
                price=poi.get('price', ''),
                description=poi.get('description', ''),
                opening_hours=poi.get('opening_hours', ''),
                best_time=poi.get('best_time', ''),
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
        budget = estimate_budget(request.itinerary, request.travelers, request.budget_level, None, request.intercity_transport)
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
    
    raise HTTPException(status_code=501, detail="路线优化接口尚未实现真实优化逻辑，已禁用占位返回")

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
        route = travel_domain_service.calculate_route(request.origin, request.destination, request.mode)
        return route
        
    except Exception as e:
        logger.error(f"Error calculating route: {e}")
        raise HTTPException(status_code=500, detail="路线计算失败")


@router.post("/route/map")
@router.post("/route/tencent")
async def calculate_map_trip_routes(request: TencentRouteRequest):
    """
    计算多日路线。

    前端小程序原生 map 组件使用 GCJ-02 坐标渲染。后端优先使用可用地图服务生成道路 polyline，
    如果真实路线规划不可用，则返回坐标直线兜底，避免地图大图页失败。
    """
    logger.info("Calculating map routes for %s day segments by %s", len(request.segments), request.mode)

    try:
        segments = []
        for segment in request.segments:
            if len(segment.points) < 2:
                continue
            route = _plan_day_map_route(
                [point.model_dump() for point in segment.points],
                request.mode,
            )
            segments.append({
                "dayIndex": segment.dayIndex,
                **route,
            })
        return {"mode": request.mode, "segments": segments}
    except RuntimeError as exc:
        logger.error("Map route calculation error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Error calculating map routes: %s", exc)
        raise HTTPException(status_code=500, detail="地图路线规划失败，请稍后重试")

@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "AI Travel Planner",
        "version": settings.APP_VERSION
    }
