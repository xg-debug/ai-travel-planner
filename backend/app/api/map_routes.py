import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.map_route_service import plan_day_map_route

logger = logging.getLogger(__name__)
router = APIRouter()


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


@router.post("/route/map")
@router.post("/route/tencent")
async def calculate_map_trip_routes(request: TencentRouteRequest):
    logger.info("Calculating map routes for %s day segments by %s", len(request.segments), request.mode)

    try:
        segments = []
        for segment in request.segments:
            if len(segment.points) < 2:
                continue
            route = plan_day_map_route(
                [point.model_dump() for point in segment.points],
                request.mode,
            )
            segments.append(
                {
                    "dayIndex": segment.dayIndex,
                    **route,
                }
            )
        return {"mode": request.mode, "segments": segments}
    except RuntimeError as exc:
        logger.error("Map route calculation error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Error calculating map routes: %s", exc)
        raise HTTPException(status_code=500, detail="地图路线规划失败，请稍后重试")
