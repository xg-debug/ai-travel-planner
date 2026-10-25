import unittest
from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.api.trip_plans import TripDayPatch, update_trip_day
from app.core.database import Base
from app.models.trip_plan import TripPlan
from app.models.user import User


class TripDayPatchTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.user = SimpleNamespace(id="user-1")
        payload = {
            "id": "plan-1", "destination": "杭州", "startDate": "2026-10-25", "endDate": "2026-10-25",
            "travelers": 2, "interests": [],
            "budget": {"total": 300, "currency": "CNY", "categories": [
                {"name": "餐饮", "amount": 100, "planned": 100},
                {"name": "门票", "amount": 200, "planned": 200},
            ]},
            "days": [{"date": "2026-10-25", "activities": [
                {"id": "a", "type": "food", "cost": 40, "title": "午餐"},
            ]}],
        }
        with self.sessions.begin() as db:
            db.add(User(id="user-1", email="trip@example.com", password_hash="hash", name="Traveler"))
            row = TripPlan(id="plan-1", user_id=self.user.id, destination="杭州", start_date="2026-10-25", end_date="2026-10-25")
            row.sync_from_payload(payload)
            db.add(row)

    def tearDown(self):
        self.engine.dispose()

    def test_day_patch_reconciles_budget_and_rejects_stale_version(self):
        day = {"date": "different-date", "activities": [{"id": "a", "type": "food", "cost": 70, "title": "午餐"}]}
        with self.sessions() as db:
            result = update_trip_day("plan-1", 0, TripDayPatch(version=1, day=day), current_user=self.user, db=db)
        self.assertEqual(result["version"], 2)
        self.assertEqual(result["days"][0]["date"], "2026-10-25")
        self.assertEqual(result["days"][0]["totalCost"], 70)
        self.assertEqual(result["budget"]["total"], 330)
        self.assertTrue(result["days"][0]["routeNeedsRefresh"])
        with self.sessions() as db, self.assertRaises(HTTPException) as raised:
            update_trip_day("plan-1", 0, TripDayPatch(version=1, day=day), current_user=self.user, db=db)
        self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
