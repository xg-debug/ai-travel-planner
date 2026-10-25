from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from contextvars import copy_context
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generator, Protocol

from app.trip_planning.events import PlanningEvent, progress_for_step

logger = logging.getLogger(__name__)

EventSink = Callable[[str, str, Dict[str, Any] | None], None]


class TripPlanner(Protocol):
    def run(
        self,
        state: Dict[str, Any],
        emit: EventSink | None = None,
    ) -> Dict[str, Any]: ...


@dataclass(frozen=True)
class _WorkerFailure:
    error: BaseException


_END = object()


class TripPlanningHarness:
    """Runs a planner with one observable lifecycle and stable event protocol.

    The planner owns reasoning and tool selection. The harness owns run identity,
    monotonic progress, isolation from the request thread and result delivery.
    """

    def __init__(self, planner: TripPlanner) -> None:
        self._planner = planner

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        final_state: Dict[str, Any] | None = None
        for event in self.stream(initial_state):
            if event["event"] == "result":
                final_state = dict((event.get("data") or {}).get("state") or {})
        if final_state is None:
            raise RuntimeError("行程规划未生成最终结果")
        return final_state

    def stream(self, initial_state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        run_id = uuid.uuid4().hex
        started_at = time.monotonic()
        events: queue.Queue[Any] = queue.Queue()
        sequence = 0
        highest_progress = 0
        state = dict(initial_state)

        def emit(step: str, message: str, detail: Dict[str, Any] | None = None) -> None:
            nonlocal sequence, highest_progress
            sequence += 1
            highest_progress = max(highest_progress, progress_for_step(step))
            event = PlanningEvent(
                run_id=run_id,
                sequence=sequence,
                step=step,
                message=message,
                progress=highest_progress,
                detail=detail or {},
            )
            events.put({"event": "status", "data": event.as_payload()})

        def worker() -> None:
            try:
                emit("request_analysis", "正在理解需求并建立本次旅行的研究计划")
                result = self._planner.run(state, emit=emit)
                result["agent_run"] = {
                    "run_id": run_id,
                    "duration_ms": round((time.monotonic() - started_at) * 1000),
                    **dict(result.get("agent_run") or {}),
                }
                emit("summary", "正在整理路线、预算与旅行提醒")
                events.put({"event": "partial_result", "data": {"state": dict(result)}})
                events.put({"event": "result", "data": {"state": dict(result)}})
            except BaseException as exc:
                logger.exception("Trip planning run failed run_id=%s", run_id)
                events.put(_WorkerFailure(exc))
            finally:
                events.put(_END)

        context = copy_context()
        threading.Thread(
            target=lambda: context.run(worker),
            name=f"trip-planning-{run_id[:8]}",
            daemon=True,
        ).start()

        while True:
            item = events.get()
            if item is _END:
                return
            if isinstance(item, _WorkerFailure):
                raise item.error
            yield item
