import asyncio
import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.trip_schemas import TripPlanningRequest, TripResponse
from app.trip_planning.errors import classify_planning_error
from app.trip_planning.jobs import trip_planning_job_service
from app.trip_planning import trip_planning_workflow
from app.trip_planning.response import build_trip_response
from app.trip_planning.state import WORKFLOW_STEP_PROGRESS, trip_request_to_state, validate_trip_state

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/planning", response_model=TripResponse)
async def plan_trip(request: TripPlanningRequest):
    state = trip_request_to_state(request)
    logger.info("Planning trip: %s for %s days", state["city"], state["days"])

    try:
        validate_trip_state(state)
        result = trip_planning_workflow.run(state)
        response = build_trip_response(result)
        if not response.itinerary:
            final_output = result.get("final_output") or response.plan or ""
            if "降级" not in final_output and "精简" not in final_output:
                raise HTTPException(status_code=502, detail="AI未生成可用行程，请稍后重试")

        logger.info("Trip planned successfully for %s", state.get("city"))
        return response
    except ValueError as exc:
        logger.error("Validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error planning trip: %s", exc)
        classified = classify_planning_error(exc)
        status_code = 402 if classified["code"] == "LLM_INSUFFICIENT_BALANCE" else 503 if not classified["retryable"] else 500
        raise HTTPException(status_code=status_code, detail=classified)


@router.post("/planning/jobs")
async def start_plan_job(request: TripPlanningRequest):
    state = trip_request_to_state(request)
    logger.info("Starting plan job: %s for %s days", state["city"], state["days"])
    try:
        validate_trip_state(state)
    except ValueError as exc:
        logger.error("Validation error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))

    return trip_planning_job_service.start(state)


@router.get("/planning/jobs/{job_id}")
async def get_plan_job(job_id: str):
    job = trip_planning_job_service.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="规划任务不存在或已过期")
    return job


@router.post("/planning/stream")
async def plan_trip_stream(request: TripPlanningRequest):
    state = trip_request_to_state(request)
    logger.info("Streaming plan request: %s %s days", state["city"], state["days"])

    async def event_generator():
        try:
            validate_trip_state(state)
            final_state = None
            for event in trip_planning_workflow.stream(state):
                await asyncio.sleep(0)
                if event["event"] == "status":
                    payload = dict(event["data"] or {})
                    step = str(payload.get("step") or "")
                    payload["progress"] = WORKFLOW_STEP_PROGRESS.get(step, 0)
                    yield _sse("status", payload)
                    continue
                if event["event"] == "partial_result":
                    partial_state = dict((event.get("data") or {}).get("state", {}) or {})
                    if partial_state:
                        yield _sse("partial_result", build_trip_response(partial_state).model_dump())
                    continue
                if event["event"] == "result":
                    final_state = event["data"]["state"]

            response = build_trip_response(final_state or {})
            if not response.itinerary:
                raise ValueError("AI未生成可用行程")

            yield _sse("result", response.model_dump())
            yield _sse("done", {"ok": True})
        except Exception as exc:
            logger.exception("Error in stream planning: %s", exc)
            yield _sse("error", classify_planning_error(exc))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"
