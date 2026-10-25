import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # register all models before create_all
from app.api.admin import get_agent_run, list_agent_runs
from app.core.database import Base
from app.core.llm import invoke_llm_with_fallback
from app.models.agent_trace import AgentRun, AgentTraceEvent
from app.trip_planning.trace import begin_run, bind_run, finish_run, record_event, safe_text


class AgentTraceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.patch = patch("app.trip_planning.trace.SessionLocal", self.sessions)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.engine.dispose()

    def test_model_and_tool_events_are_saved_without_prompt_or_secret(self):
        run_id = begin_run(source="job", city="杭州", days=1, job_id="job-1")
        response = SimpleNamespace(
            content="{\"ok\":true}", usage_metadata={"input_tokens": 12, "output_tokens": 5},
            response_metadata={"finish_reason": "stop"},
        )
        with bind_run(run_id), \
             patch("app.core.llm.get_llm_provider", return_value="deepseek"), \
             patch("app.core.llm.get_llm_model", return_value="deepseek-flash"), \
             patch("app.core.llm._try_create_llm", return_value=SimpleNamespace(invoke=lambda _: response)):
            invoke_llm_with_fallback("Private itinerary prompt", 0, 80, operation="planner")
            record_event("tool", "search_attractions", "completed", input_summary={"key": "sk-abcdefghijklmnop"})
        finish_run(run_id, "completed", result_summary={"days": 1})

        with self.sessions() as db:
            run = db.get(AgentRun, run_id)
            events = db.execute(select(AgentTraceEvent).where(AgentTraceEvent.run_id == run_id).order_by(AgentTraceEvent.id)).scalars().all()
            page = list_agent_runs(page=1, page_size=20, status=None, search=None, _principal=None, db=db)
            detail = get_agent_run(run_id, _principal=None, db=db)
        self.assertEqual((run.status, run.model_calls, run.tool_calls), ("completed", 1, 1))
        self.assertEqual(events[0].model, "deepseek-flash")
        self.assertEqual(events[0].output_summary["usage"]["input_tokens"], 12)
        self.assertNotIn("Private itinerary prompt", str(detail))
        self.assertNotIn("sk-abcdefghijklmnop", str(detail))
        self.assertEqual(page["total"], 1)
        self.assertEqual(len(detail["events"]), 2)

    def test_retry_interrupts_previous_attempt(self):
        previous = begin_run(source="job", city="杭州", days=1, job_id="job-1")
        current = begin_run(source="job", city="杭州", days=1, job_id="job-1", attempt=2)
        with self.sessions() as db:
            self.assertEqual(db.get(AgentRun, previous).status, "interrupted")
            self.assertEqual(db.get(AgentRun, current).status, "running")
        self.assertNotIn("secret123456789", safe_text("api_key=secret123456789"))


if __name__ == "__main__":
    unittest.main()
