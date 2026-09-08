from __future__ import annotations

import unittest

from app.trip_planning.harness import TripPlanningHarness
from app.trip_planning.mcp_agent_planner import _tool_status, _validate_tool_trace


class _FakePlanner:
    def run(self, state, emit=None):
        assert emit is not None
        emit("hotel_search", "已获得住宿", {"tool": "maps_text_search"})
        # The agent may call tools in a different order. Progress must not regress.
        emit("weather_lookup", "已获得天气", {"tool": "maps_weather"})
        return {
            **state,
            "plan": [{"day": 1, "activities": [{"title": "外滩"}]}],
        }


class TripPlanningHarnessTests(unittest.TestCase):
    def test_stream_has_stable_identity_sequence_and_monotonic_progress(self):
        events = list(TripPlanningHarness(_FakePlanner()).stream({"city": "上海"}))
        statuses = [event["data"] for event in events if event["event"] == "status"]

        self.assertTrue(statuses)
        self.assertEqual(
            [item["sequence"] for item in statuses],
            list(range(1, len(statuses) + 1)),
        )
        self.assertEqual(len({item["run_id"] for item in statuses}), 1)
        self.assertEqual(
            [item["progress"] for item in statuses],
            sorted(item["progress"] for item in statuses),
        )
        self.assertEqual(events[-1]["event"], "result")

    def test_tool_status_uses_search_intent(self):
        step, _ = _tool_status(
            "maps_text_search",
            {"keywords": "上海酒店"},
            completed=False,
        )
        self.assertEqual(step, "hotel_search")

    def test_quality_gate_requires_search_and_weather(self):
        with self.assertRaisesRegex(RuntimeError, "地点检索"):
            _validate_tool_trace([{"tool": "maps_weather", "ok": True}])

        _validate_tool_trace(
            [
                {"tool": "maps_text_search", "ok": True},
                {"tool": "maps_weather", "ok": True},
            ]
        )


if __name__ == "__main__":
    unittest.main()
