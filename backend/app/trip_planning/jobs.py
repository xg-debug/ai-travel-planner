import logging
import threading
import time
import uuid
from typing import Any, Dict

from app.trip_planning import trip_planning_workflow
from app.trip_planning.errors import classify_planning_error
from app.trip_planning.response import build_trip_response
from app.trip_planning.state import WORKFLOW_STEP_PROGRESS

logger = logging.getLogger(__name__)

PLAN_JOB_TTL_SECONDS = 60 * 60


class TripPlanningJobService:
    def __init__(self) -> None:
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def start(self, state: Dict[str, Any]) -> Dict[str, str]:
        self._cleanup()
        job_id = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "running",
                "city": state.get("city", ""),
                "days": state.get("days", 0),
                "step": "request_analysis",
                "message": "规划任务已启动",
                "progress": WORKFLOW_STEP_PROGRESS["request_analysis"],
                "created_at": now,
                "updated_at": now,
                "result": None,
                "partial_result": None,
                "error": "",
                "error_code": "",
                "retryable": True,
            }
        threading.Thread(target=self._run, args=(job_id, state), daemon=True).start()
        return {"job_id": job_id, "status": "running"}

    def get(self, job_id: str) -> Dict[str, Any] | None:
        self._cleanup()
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            return {
                "job_id": job.get("job_id", job_id),
                "status": job.get("status", "running"),
                "city": job.get("city", ""),
                "days": job.get("days", 0),
                "step": job.get("step", ""),
                "message": job.get("message", ""),
                "progress": job.get("progress", 0),
                "result": job.get("result"),
                "partial_result": job.get("partial_result"),
                "error": job.get("error", ""),
                "error_code": job.get("error_code", ""),
                "retryable": job.get("retryable", True),
                "created_at": job.get("created_at"),
                "updated_at": job.get("updated_at"),
            }

    def _cleanup(self) -> None:
        now = time.time()
        with self._lock:
            expired = [
                job_id
                for job_id, job in self._jobs.items()
                if now - float(job.get("updated_at", job.get("created_at", now)) or now) > PLAN_JOB_TTL_SECONDS
            ]
            for job_id in expired:
                self._jobs.pop(job_id, None)

    def _update(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            job = dict(self._jobs.get(job_id, {}))
            job.update(changes)
            job["updated_at"] = time.time()
            self._jobs[job_id] = job

    def _update_status(self, job_id: str, payload: Dict[str, Any]) -> None:
        step = str(payload.get("step") or "").strip()
        message = str(payload.get("message") or "").strip()
        if not step and not message:
            return
        logger.info("Plan job progress job_id=%s step=%s message=%s", job_id, step, message)
        self._update(
            job_id,
            step=step,
            message=message,
            progress=WORKFLOW_STEP_PROGRESS.get(step, 0),
        )

    def _run(self, job_id: str, state: Dict[str, Any]) -> None:
        logger.info("Plan job started job_id=%s city=%s days=%s", job_id, state.get("city"), state.get("days"))
        try:
            result: Dict[str, Any] = {}
            for event in trip_planning_workflow.stream(state):
                event_name = event.get("event")
                data = event.get("data") or {}
                if event_name == "status":
                    self._update_status(job_id, data)
                    continue
                if event_name == "result":
                    result = dict(data.get("state", {}) or {})
                if event_name == "partial_result":
                    partial_state = dict(data.get("state", {}) or {})
                    if partial_state:
                        self._update(job_id, partial_result=build_trip_response(partial_state).model_dump())
            if not result:
                raise RuntimeError("行程规划未生成最终结果")
            response = build_trip_response(result)
            if not response.itinerary:
                final_output = result.get("final_output") or response.plan or ""
                if "降级" not in final_output and "精简" not in final_output:
                    raise RuntimeError("AI未生成可用行程，请稍后重试")
            self._update(
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
            classified = classify_planning_error(exc)
            self._update(
                job_id,
                status="failed",
                progress=0,
                error=classified["message"],
                error_code=classified["code"],
                retryable=classified["retryable"],
                raw_error=str(exc),
            )


trip_planning_job_service = TripPlanningJobService()
