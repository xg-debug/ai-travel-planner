"""Database-backed planning jobs. API processes never execute a planning run."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select, update

from app.core.database import SessionLocal
from app.models.planning_job import PlanningJob
from app.trip_planning.errors import classify_planning_error
from app.trip_planning.response import build_trip_response
from app.trip_planning.state import WORKFLOW_STEP_PROGRESS
from app.trip_planning.trace import begin_run, bind_run, finish_run, record_event

logger = logging.getLogger(__name__)
LEASE_SECONDS = 120
MAX_ATTEMPTS = 3


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _public_job(row: PlanningJob) -> dict[str, Any]:
    return {
        "job_id": row.id,
        "status": row.status,
        "city": row.request_json.get("city", ""),
        "days": row.request_json.get("days", 0),
        "step": row.step,
        "message": row.message,
        "progress": row.progress,
        "result": row.result_json,
        "partial_result": None,
        "error": row.error or "",
        "error_code": row.error_code or "",
        "retryable": row.retryable,
        "created_at": row.created_at.timestamp(),
        "updated_at": row.updated_at.timestamp(),
    }


class TripPlanningJobService:
    def start(self, state: dict[str, Any], user_id: str | None = None) -> dict[str, str]:
        guest_token = secrets.token_urlsafe(32) if user_id is None else None
        job_id = str(uuid.uuid4())
        row = PlanningJob(
            id=job_id,
            user_id=user_id,
            guest_token_hash=_token_hash(guest_token) if guest_token else None,
            request_json=_json_safe(state),
        )
        with SessionLocal.begin() as db:
            if user_id:
                active = db.execute(
                    select(PlanningJob.id).where(
                        PlanningJob.user_id == user_id,
                        PlanningJob.status.in_(["queued", "running"]),
                    ).limit(2)
                ).all()
                if len(active) >= 2:
                    raise ValueError("已有两个规划任务正在进行，请等待完成")
            db.add(row)
        response = {"job_id": job_id, "status": "queued"}
        if guest_token:
            response["guest_token"] = guest_token
        return response

    def get(self, job_id: str, *, user_id: str | None = None, guest_token: str | None = None) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.get(PlanningJob, job_id)
            if row is None:
                return None
            if row.user_id is not None:
                if row.user_id != user_id:
                    return None
            elif not guest_token or not secrets.compare_digest(row.guest_token_hash or "", _token_hash(guest_token)):
                return None
            return _public_job(row)

    def claim(self) -> tuple[str, int] | None:
        """Claim a queued job or an expired lease; attempt guards stale workers."""
        now = _utcnow()
        with SessionLocal.begin() as db:
            row = db.execute(
                select(PlanningJob)
                .where(or_(PlanningJob.status == "queued", (PlanningJob.status == "running") & (PlanningJob.lease_until < now)))
                .order_by(PlanningJob.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).scalar_one_or_none()
            if row is None:
                return None
            if row.attempt >= MAX_ATTEMPTS:
                row.status = "failed"
                row.error = "规划任务连续中断，请重新生成"
                row.error_code = "PLANNING_JOB_INTERRUPTED"
                row.retryable = True
                return None
            row.status = "running"
            row.attempt += 1
            row.lease_until = now + timedelta(seconds=LEASE_SECONDS)
            row.message = "正在继续规划" if row.attempt > 1 else "规划任务已启动"
            row.updated_at = now
            return row.id, row.attempt

    def snapshot(self, job_id: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
        with SessionLocal() as db:
            row = db.get(PlanningJob, job_id)
            if row is None:
                raise RuntimeError("规划任务不存在")
            return dict(row.request_json), dict(row.checkpoint_json) if row.checkpoint_json else None

    def update(self, job_id: str, attempt: int, **changes: Any) -> bool:
        for key in ("checkpoint_json", "result_json"):
            if changes.get(key) is not None:
                changes[key] = _json_safe(changes[key])
        changes["updated_at"] = _utcnow()
        with SessionLocal.begin() as db:
            result = db.execute(
                update(PlanningJob)
                .where(PlanningJob.id == job_id, PlanningJob.attempt == attempt, PlanningJob.status == "running")
                .values(**changes)
            )
            return result.rowcount == 1

    def heartbeat(self, job_id: str, attempt: int) -> bool:
        return self.update(job_id, attempt, lease_until=_utcnow() + timedelta(seconds=LEASE_SECONDS))

    def run_claimed(self, job_id: str, attempt: int) -> None:
        from app.trip_planning.agent_planner import plan_execute_replan_agent

        state, checkpoint = self.snapshot(job_id)
        with SessionLocal() as db:
            owner = db.get(PlanningJob, job_id)
            user_id = owner.user_id if owner else None
        run_id = begin_run(source="job", city=state.get("city", ""), days=int(state.get("days") or 1), job_id=job_id, attempt=attempt, user_id=user_id)

        def emit(step: str, message: str, _detail: dict[str, Any] | None = None) -> None:
            self.update(
                job_id, attempt,
                step=step, message=message,
                progress=WORKFLOW_STEP_PROGRESS.get(step, 0),
                lease_until=_utcnow() + timedelta(seconds=LEASE_SECONDS),
            )
            record_event("phase", step, "progress", output_summary={"message": message, "progress": WORKFLOW_STEP_PROGRESS.get(step, 0)})

        def save_checkpoint(_stage: str, working: dict[str, Any]) -> None:
            if not self.update(job_id, attempt, checkpoint_json=working):
                raise RuntimeError("规划任务执行权已转移")
            record_event("checkpoint", _stage, "completed", output_summary={"iteration": working.get("iteration", 0)})

        with bind_run(run_id):
            try:
                result = plan_execute_replan_agent.run(state, emit=emit, checkpoint=save_checkpoint, resume=checkpoint)
                response = build_trip_response(result)
                if not response.itinerary:
                    raise RuntimeError("AI未生成可用行程，请稍后重试")
                summary = {
                    "days": len(response.itinerary or []),
                    "activities": sum(len(day.get("activities") or []) for day in response.itinerary or []),
                    "estimated_budget": (getattr(response, "estimated_budget", None) or {}).get("total"),
                    "quality_score": (getattr(response, "quality_score", None) or {}).get("score"),
                }
                self.update(
                    job_id, attempt, status="completed", step="summary", message="行程规划已完成",
                    progress=100, result_json=response.model_dump(), checkpoint_json=None,
                    lease_until=None, error=None, error_code=None,
                )
                record_event("result", "itinerary", "completed", output_summary=summary)
                finish_run(run_id, "completed", result_summary=summary)
            except Exception as exc:
                logger.exception("Plan job failed job_id=%s attempt=%s", job_id, attempt)
                classified = classify_planning_error(exc)
                self.update(
                    job_id, attempt, status="failed", lease_until=None,
                    error=classified["message"], error_code=classified["code"],
                    retryable=classified["retryable"], message="规划失败",
                )
                record_event("result", "itinerary", "failed", error_code=classified["code"], output_summary={"message": classified["message"]})
                finish_run(run_id, "failed", error_code=classified["code"])


trip_planning_job_service = TripPlanningJobService()
