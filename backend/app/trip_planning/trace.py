"""Bounded, credential-free Agent traces persisted independently of job state."""

from __future__ import annotations

import logging
import re
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.agent_trace import AgentRun, AgentTraceEvent

logger = logging.getLogger(__name__)
_current_run: ContextVar[str | None] = ContextVar("agent_trace_run", default=None)
_secret_pattern = re.compile(r"(?i)(bearer\s+|(?:sk|ds)-)[A-Za-z0-9_\-]{12,}")
_query_secret_pattern = re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|token|key)\s*[=:]\s*)[^\s&,;]+")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\x00", " ").strip()
    text = _secret_pattern.sub("[REDACTED]", text)
    text = _query_secret_pattern.sub(r"\1[REDACTED]", text)
    return text[:limit]


def _bounded(value: Any, depth: int = 0) -> Any:
    if depth >= 3:
        return safe_text(value, 100)
    if isinstance(value, dict):
        return {safe_text(k, 60): _bounded(v, depth + 1) for k, v in list(value.items())[:16]}
    if isinstance(value, (list, tuple)):
        return [_bounded(item, depth + 1) for item in list(value)[:8]]
    if isinstance(value, str):
        return safe_text(value, 300)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return safe_text(value, 100)


def begin_run(*, source: str, city: str, days: int, job_id: str | None = None, attempt: int = 1, user_id: str | None = None) -> str | None:
    run_id = str(uuid.uuid4())
    try:
        with SessionLocal.begin() as db:
            if job_id:
                previous = db.execute(select(AgentRun).where(AgentRun.job_id == job_id, AgentRun.status == "running")).scalars().all()
                now = _now()
                for row in previous:
                    row.status = "interrupted"
                    row.completed_at = now
                    row.duration_ms = max(0, int((now - row.created_at).total_seconds() * 1000))
            db.add(AgentRun(
                id=run_id, job_id=job_id, user_id=user_id, source=source[:20],
                attempt=attempt, city=safe_text(city, 100), days=max(1, days),
            ))
        return run_id
    except Exception as exc:
        logger.warning("Agent trace unavailable on start: %s", type(exc).__name__)
        return None


@contextmanager
def bind_run(run_id: str | None) -> Iterator[None]:
    token = _current_run.set(run_id)
    try:
        yield
    finally:
        _current_run.reset(token)


def current_run_id() -> str | None:
    return _current_run.get()


def record_event(
    kind: str,
    name: str,
    status: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    endpoint: str | None = None,
    duration_ms: int | None = None,
    input_summary: dict[str, Any] | None = None,
    output_summary: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> None:
    run_id = _current_run.get()
    if not run_id:
        return
    try:
        with SessionLocal.begin() as db:
            db.add(AgentTraceEvent(
                run_id=run_id, kind=kind[:24], name=name[:120], status=status[:20],
                provider=provider[:50] if provider else None,
                model=model[:120] if model else None,
                endpoint=endpoint[:120] if endpoint else None,
                duration_ms=max(0, int(duration_ms)) if duration_ms is not None else None,
                input_summary=_bounded(input_summary) if input_summary else None,
                output_summary=_bounded(output_summary) if output_summary else None,
                error_code=error_code[:80] if error_code else None,
            ))
            row = db.get(AgentRun, run_id)
            if row:
                if kind == "model" and status in {"completed", "failed"}:
                    row.model_calls += 1
                elif kind == "tool":
                    row.tool_calls += 1
    except Exception as exc:
        logger.warning("Agent trace event unavailable run_id=%s type=%s", run_id, type(exc).__name__)


def finish_run(run_id: str | None, status: str, *, error_code: str | None = None, result_summary: dict[str, Any] | None = None) -> None:
    if not run_id:
        return
    try:
        with SessionLocal.begin() as db:
            row = db.get(AgentRun, run_id)
            if not row or row.status != "running":
                return
            now = _now()
            row.status = status[:20]
            row.completed_at = now
            row.duration_ms = max(0, int((now - row.created_at).total_seconds() * 1000))
            row.error_code = error_code[:80] if error_code else None
            row.result_summary = _bounded(result_summary) if result_summary else None
    except Exception as exc:
        logger.warning("Agent trace unavailable on finish run_id=%s type=%s", run_id, type(exc).__name__)


def summarize_tool_result(value: dict[str, Any] | None) -> dict[str, Any]:
    result = value or {}
    summary: dict[str, Any] = {}
    for key, item in result.items():
        if isinstance(item, list):
            summary[f"{key}_count"] = len(item)
            names = [safe_text(entry.get("name") or entry.get("title"), 60) for entry in item[:3] if isinstance(entry, dict)]
            if names:
                summary[f"{key}_sample"] = names
        elif key == "intercity_transport" and isinstance(item, dict):
            summary["intercity_transport"] = {"mode": item.get("mode"), "total_cost": item.get("total_cost")}
        elif key == "weather_data" and isinstance(item, dict):
            summary["forecast_count"] = len(item.get("forecast") or [])
    return summary or {"result_keys": list(result)[:10]}
