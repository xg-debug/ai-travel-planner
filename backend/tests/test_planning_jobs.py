import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # register all foreign-key tables
from app.core.database import Base
from app.models.planning_job import PlanningJob
from app.models.agent_trace import AgentRun, AgentTraceEvent
from app.trip_planning.jobs import TripPlanningJobService


class PlanningJobTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.patch = patch("app.trip_planning.jobs.SessionLocal", self.sessions)
        self.patch.start()
        self.trace_patch = patch("app.trip_planning.trace.SessionLocal", self.sessions)
        self.trace_patch.start()
        self.service = TripPlanningJobService()

    def tearDown(self):
        self.patch.stop()
        self.trace_patch.stop()
        self.engine.dispose()

    def test_guest_token_protects_job_and_worker_claims_it(self):
        started = self.service.start({"city": "杭州", "days": 2})
        self.assertEqual(started["status"], "queued")
        self.assertIsNone(self.service.get(started["job_id"]))
        self.assertIsNone(self.service.get(started["job_id"], guest_token="wrong"))
        self.assertEqual(self.service.get(started["job_id"], guest_token=started["guest_token"])["status"], "queued")
        claimed = self.service.claim()
        self.assertEqual(claimed[0], started["job_id"])
        self.assertTrue(self.service.update(claimed[0], claimed[1], step="attraction_search", progress=30))
        self.assertEqual(self.service.get(started["job_id"], guest_token=started["guest_token"])["progress"], 30)

    def test_expired_lease_resumes_from_checkpoint_and_fences_old_worker(self):
        started = self.service.start({"city": "杭州", "days": 2}, user_id="user-1")
        first = self.service.claim()
        self.service.update(first[0], first[1], checkpoint_json={"_phase": "searched", "city": "杭州"})
        with self.sessions.begin() as db:
            row = db.get(PlanningJob, first[0])
            row.lease_until = datetime.utcnow() - timedelta(seconds=1)
        second = self.service.claim()
        self.assertEqual(second, (first[0], first[1] + 1))
        self.assertFalse(self.service.update(first[0], first[1], status="completed"))
        self.assertEqual(self.service.snapshot(first[0])[1]["_phase"], "searched")
        self.assertIsNone(self.service.get(first[0], user_id="other-user"))
        self.assertEqual(self.service.get(first[0], user_id="user-1")["status"], "running")

    def test_worker_persists_final_result_after_checkpoint(self):
        started = self.service.start({"city": "杭州", "days": 1})
        job_id, attempt = self.service.claim()

        def fake_run(state, emit, checkpoint, resume):
            self.assertIsNone(resume)
            checkpoint("searched", {**state, "_phase": "searched"})
            emit("itinerary_synthesis", "正在编排行程")
            return {**state, "plan": [{"activities": [{"title": "西湖"}]}]}

        fake_response = SimpleNamespace(itinerary=[{"activities": [{"title": "西湖"}]}], model_dump=lambda: {"itinerary": [{"activities": [{"title": "西湖"}]}]})
        with patch("app.trip_planning.agent_planner.plan_execute_replan_agent.run", side_effect=fake_run), \
             patch("app.trip_planning.jobs.build_trip_response", return_value=fake_response):
            self.service.run_claimed(job_id, attempt)
        result = self.service.get(job_id, guest_token=started["guest_token"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["progress"], 100)
        self.assertEqual(result["result"]["itinerary"][0]["activities"][0]["title"], "西湖")
        self.assertIsNone(self.service.snapshot(job_id)[1])
        with self.sessions() as db:
            run = db.execute(select(AgentRun).where(AgentRun.job_id == job_id)).scalar_one()
            events = db.execute(select(AgentTraceEvent).where(AgentTraceEvent.run_id == run.id)).scalars().all()
        self.assertEqual(run.status, "completed")
        self.assertTrue(any(event.kind == "result" for event in events))


if __name__ == "__main__":
    unittest.main()
