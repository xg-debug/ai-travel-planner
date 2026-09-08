from __future__ import annotations

import unittest
from unittest.mock import patch

from app.trip_planning.agent_planner import PlanExecuteReplanAgent
from app.domain.travel_domain import normalize_image_url
from app.trip_planning.intercity_transport import plan_intercity_transport
from app.trip_planning.nodes import _enrich_plan_media
from app.trip_planning.tool_executor import TripPlanningToolbox


class _FakeToolbox:
    def execute_one(self, name, _args, _state):
        if name == "get_weather":
            return {"weather_data": {"forecast": [{"date": "2026-09-12"}]}}
        if name == "search_attractions":
            return {"attraction_candidates": [{"name": "西湖"}]}
        raise AssertionError(f"unexpected tool: {name}")


class AgentPlannerTests(unittest.TestCase):
    def test_model_balance_fallback_is_disclosed_in_response(self):
        from app.trip_planning.response import build_trip_response

        state = {}
        events = []
        emit = lambda step, message, detail: events.append(detail)
        for _ in range(2):
            PlanExecuteReplanAgent._record_fallback(state, RuntimeError('402 Insufficient Balance'), emit)
        result = build_trip_response(state)
        self.assertEqual(len(result.planning_warnings), 1)
        self.assertIn('余额不足', result.planning_warnings[0])
        self.assertIn('基础行程', result.planning_warnings[0])
        self.assertTrue(events[0]['degraded'])
        from app.api.trip_plans import TripPlanPayload
        stored = TripPlanPayload(destination='杭州', startDate='2026-09-07', endDate='2026-09-07', travelers=2,
                                 planningWarnings=result.planning_warnings).to_storage_dict()
        self.assertEqual(stored['planningWarnings'], result.planning_warnings)

    def test_agent_executes_bounded_plan_and_emits_progress(self):
        agent = PlanExecuteReplanAgent(max_iterations=1)
        agent._toolbox = _FakeToolbox()
        events = []

        with (
            patch(
                "app.trip_planning.agent_planner.planner_node",
                return_value={
                    "next_actions": [
                        {"name": "get_weather", "args": {}},
                        {"name": "search_attractions", "args": {}},
                    ]
                },
            ),
            patch(
                "app.trip_planning.agent_planner.finalizer_node",
                return_value={"plan": [{"day": 1, "activities": [{"title": "西湖"}]}]},
            ),
        ):
            result = agent.run(
                {"city": "杭州", "days": 1},
                emit=lambda step, message, detail=None: events.append((step, message, detail)),
            )

        self.assertEqual(result["agent_run"]["planner"], "plan_execute_replan")
        self.assertEqual(result["agent_run"]["executed_actions"], ["get_weather", "search_attractions"])
        self.assertIn("weather_lookup", [event[0] for event in events])
        self.assertIn("itinerary_synthesis", [event[0] for event in events])

    @patch("app.trip_planning.intercity_transport._plan_with_llm")
    @patch("app.trip_planning.intercity_transport._query_route_metrics", return_value=(175.0, 150))
    def test_intercity_transport_uses_map_without_nested_llm(self, _metrics, nested_llm):
        result = plan_intercity_transport(
            "上海",
            "杭州",
            2,
            start_date="2026-09-12",
            days=1,
            budget_amount=7000,
        )

        nested_llm.assert_not_called()
        self.assertEqual(result["outbound"]["source"], "map")
        self.assertEqual(result["outbound"]["mode"], "高铁/动车")
        self.assertGreater(result["total_cost"], 0)
        self.assertTrue(result["outbound"]["alternatives"])

    @patch("app.trip_planning.tool_executor._search_many")
    def test_hotel_tool_uses_verified_map_candidates(self, search_many):
        search_many.return_value = [
            {
                "id": "restaurant-1",
                "name": "杭州中心四季酒店·大堂酒廊",
                "type": "餐饮服务;餐饮相关场所",
                "address": "展览东路",
                "lat": 30.26,
                "lng": 120.17,
                "rating": 4.8,
                "image_url": "https://store.is.autonavi.com/lounge.jpg",
                "source": "amap",
            },
            {
                "id": "poi-1",
                "name": "杭州西湖酒店",
                "type": "住宿服务;宾馆酒店",
                "address": "西湖区",
                "lat": 30.25,
                "lng": 120.16,
                "rating": 4.7,
                "image_url": "https://store.is.autonavi.com/hotel.jpg",
                "source": "amap",
            }
        ]

        result = TripPlanningToolbox().recommend_hotels(
            {"city": "杭州", "accommodation_preference": "mid-range", "recommendations": []},
            {"areas": ["西湖景区"], "count": 3},
        )

        hotel = result["hotel_options"][0]
        self.assertEqual(hotel["source"], "amap")
        self.assertEqual(hotel["name"], "杭州西湖酒店")
        self.assertEqual(hotel["price_is_estimated"], True)
        self.assertEqual(hotel["lat"], 30.25)
        self.assertEqual(hotel["image_url"], "https://store.is.autonavi.com/hotel.jpg")

    def test_finalized_activity_restores_verified_poi_image(self):
        plan = [{"activities": [{"title": "游览西湖", "location": "西湖"}]}]
        state = {
            "city": "杭州",
            "attraction_candidates": [
                {
                    "id": "poi-west-lake",
                    "name": "西湖",
                    "lat": 30.25,
                    "lng": 120.14,
                    "image_url": "https://store.is.autonavi.com/west-lake.jpg",
                    "source": "amap",
                }
            ],
            "food_candidates": [],
            "hotel_options": [],
        }

        result = _enrich_plan_media(plan, state)

        activity = result[0]["activities"][0]
        self.assertEqual(activity["image"], "https://store.is.autonavi.com/west-lake.jpg")
        self.assertEqual(activity["source_id"], "poi-west-lake")

    def test_external_images_are_upgraded_to_https(self):
        self.assertEqual(
            normalize_image_url("http://aos-comment.amap.com/example.jpg"),
            "https://aos-comment.amap.com/example.jpg",
        )
        self.assertEqual(normalize_image_url("javascript:alert(1)"), "")


if __name__ == "__main__":
    unittest.main()
