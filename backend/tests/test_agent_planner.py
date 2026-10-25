from __future__ import annotations

import unittest
from unittest.mock import patch

from app.trip_planning.agent_planner import PlanExecuteReplanAgent
from app.domain.travel_domain import normalize_image_url
from app.trip_planning.intercity_transport import plan_intercity_transport
from app.trip_planning.itinerary import normalize_itinerary, select_state_candidate_for_activity
from app.trip_planning.nodes import _attach_consistent_hotels, _enrich_plan_media, _fallback_itinerary
from app.trip_planning.tool_executor import TripPlanningToolbox


class _FakeToolbox:
    def execute_one(self, name, _args, _state):
        if name == "get_weather":
            return {"weather_data": {"forecast": [{"date": "2026-09-12"}]}}
        if name == "search_attractions":
            return {"attraction_candidates": [
                {"id": "west-lake", "name": "西湖", "lat": 30.25, "lng": 120.14, "source": "amap"},
                {"id": "lingyin", "name": "灵隐寺", "lat": 30.24, "lng": 120.10, "source": "amap"},
            ]}
        if name == "search_foods":
            return {"food_candidates": [{"id": "restaurant", "name": "餐厅", "lat": 30.26, "lng": 120.15, "source": "amap"}]}
        if name == "recommend_hotels":
            return {"hotel_options": []}
        if name == "plan_transport":
            return {"intercity_transport": {}}
        raise AssertionError(f"unexpected tool: {name}")


class AgentPlannerTests(unittest.TestCase):
    def test_unavailable_model_skips_repeated_finalizer_call(self):
        agent = PlanExecuteReplanAgent(max_iterations=1)
        agent._toolbox = _FakeToolbox()
        with patch("app.trip_planning.agent_planner.planner_node", side_effect=RuntimeError("未检测到可用的 LLM API Key")), \
             patch("app.trip_planning.agent_planner.finalizer_node", side_effect=AssertionError("model retried")), \
             patch("app.services.map_route_service.enrich_itinerary_routes"), \
             patch("app.trip_planning.agent_planner.audit_plan", return_value={"verified_attraction_count": 1, "issues": []}):
            result = agent.run({"city": "杭州", "days": 1, "travelers": 1})
        self.assertTrue(result["plan"])
        self.assertTrue(result["_model_unavailable"])

    def test_targeted_second_pass_runs_only_missing_tool_and_checkpoints(self):
        agent = PlanExecuteReplanAgent(max_iterations=2)
        agent._toolbox = _FakeToolbox()
        checkpoints = []
        first_plan = {"next_actions": [
            {"name": "get_weather", "args": {}},
            {"name": "search_attractions", "args": {}},
        ]}
        final = {"plan": [{"activities": [{"title": "西湖"}]}],
                 "estimated_budget": {"total": 100, "breakdown": {"tickets": 100}}, "daily_budgets": []}
        with patch("app.trip_planning.agent_planner.planner_node", return_value=first_plan) as planner, \
             patch("app.trip_planning.agent_planner.finalizer_node", return_value=final) as finalizer, \
             patch("app.services.map_route_service.enrich_itinerary_routes"), \
             patch("app.trip_planning.agent_planner.budget_node", return_value={}), \
             patch("app.trip_planning.agent_planner.audit_plan", return_value={"verified_attraction_count": 1, "issues": []}):
            result = agent.run({"city": "杭州", "days": 1}, checkpoint=lambda phase, _state: checkpoints.append(phase))
        self.assertEqual(result["executed_actions"], ["get_weather", "search_attractions", "search_foods"])
        self.assertEqual(result["agent_run"]["iterations"], 2)
        self.assertIn("repairing", checkpoints)
        planner.assert_called_once()
        finalizer.assert_called_once()

    def test_second_pass_only_repairs_missing_candidates(self):
        actions = PlanExecuteReplanAgent._targeted_actions({
            "city": "杭州", "days": 2,
            "attraction_candidates": [{"id": str(i)} for i in range(4)],
            "hotel_options": [{"id": "hotel"}],
            "food_candidates": [],
        })
        self.assertEqual([item["name"] for item in actions], ["search_foods"])

    def test_resume_after_route_does_not_repeat_planning_or_tools(self):
        agent = PlanExecuteReplanAgent(max_iterations=2)
        resume = {"_phase": "routed", "city": "杭州", "days": 1, "iteration": 1,
                  "plan": [{"activities": [{"title": "西湖"}]}]}
        with patch("app.trip_planning.agent_planner.planner_node", side_effect=AssertionError("planner replayed")), \
             patch("app.trip_planning.agent_planner.finalizer_node", side_effect=AssertionError("finalizer replayed")), \
             patch("app.trip_planning.agent_planner.audit_plan", return_value={"verified_attraction_count": 1, "issues": []}):
            result = agent.run({"city": "杭州"}, resume=resume)
        self.assertEqual(result["agent_run"]["iterations"], 1)

    @patch("app.trip_planning.tool_executor._search_many")
    def test_hotel_search_does_not_turn_restaurants_into_lodging(self, search_many):
        search_many.return_value = [{
            "id": "lounge-1", "name": "西湖酒店大堂酒廊", "type": "住宿服务;餐饮服务;酒廊",
            "lat": 30.25, "lng": 120.16, "source": "amap",
        }]
        result = TripPlanningToolbox().recommend_hotels(
            {"city": "杭州", "accommodation_preference": "mid-range", "recommendations": []},
            {"areas": ["西湖"], "count": 3},
        )
        self.assertNotIn("西湖酒店大堂酒廊", [item["name"] for item in result["hotel_options"]])
        self.assertEqual(result["hotel_options"][0]["source"], "area_estimate")
        self.assertIn("暂未核验", result["planning_warnings"][0])

    def test_finalizer_cannot_replace_verified_hotel_with_invented_one(self):
        hotels = [{"id": "hotel-1", "name": "西湖酒店", "address": "西湖区", "lat": 30.25,
                   "lng": 120.16, "source": "amap", "price_estimate": "约350-600元/晚"}]
        plan = [{"hotel_recommendation": {"name": "虚构酒店", "source_id": "made-up", "price_estimate": "¥1"}}]
        result = _attach_consistent_hotels(plan, hotels)[0]["hotel_recommendation"]
        self.assertEqual(result["name"], "西湖酒店")
        self.assertEqual(result["source_id"], "hotel-1")
        self.assertEqual(result["price_estimate"], "约350-600元/晚")

    def test_finalizer_drops_unverified_hotel_without_candidates(self):
        plan = [{"hotel_recommendation": {"name": "虚构酒店"}}]
        self.assertEqual(_attach_consistent_hotels(plan, [])[0]["hotel_recommendation"], {})

    def test_unknown_ticket_price_is_not_free_admission(self):
        plan = normalize_itinerary([{"activities": [{"title": "游览西湖", "ticket_price": 0}]}],
                                   {"days": 1})
        self.assertIsNone(plan[0]["activities"][0]["ticket_price"])

    def test_candidate_matching_preserves_activity_category(self):
        state = {
            "attraction_candidates": [{"id": "attraction", "name": "西湖", "lat": 30.25, "lng": 120.14, "source": "amap"}],
            "food_candidates": [{"id": "food", "name": "楼外楼", "lat": 30.26, "lng": 120.15, "source": "amap"}],
        }
        self.assertIsNone(select_state_candidate_for_activity(
            state, {"type": "景点游览", "title": "楼外楼", "location": "楼外楼", "source_id": "food"}, []
        ))
        matched = select_state_candidate_for_activity(
            state, {"type": "美食餐饮", "title": "午餐：楼外楼", "location": "楼外楼"}, []
        )
        self.assertEqual(matched["id"], "food")

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
                return_value={"plan": [{"day": 1, "activities": [{"title": "西湖", "type": "景点游览", "location": "西湖", "source": "amap", "source_id": "west-lake", "coordinates": {"lat": 30.25, "lng": 120.14}}]}], "estimated_budget": {"total": 0, "breakdown": {}}, "daily_budgets": [{"total": 0}]},
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
                "image_url": "http://store.is.autonavi.com/hotel.jpg",
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
        self.assertEqual(hotel["image_source_id"], "poi-1")
        self.assertEqual(hotel["image_source_name"], "杭州西湖酒店")
        details = result["recommendations"][0]["item_details"][0]
        self.assertEqual(details["image_url"], "https://store.is.autonavi.com/hotel.jpg")
        self.assertEqual(details["image_source_id"], "poi-1")
        self.assertEqual(details["image_source_name"], "杭州西湖酒店")

    @patch("app.trip_planning.tool_executor.travel_domain_service.search_around")
    def test_food_recommendation_prefers_quality_poi_image(self, search_around):
        search_around.return_value = [
            {
                "id": "food-placeholder",
                "name": "普通餐厅",
                "type": "餐饮服务;中餐厅",
                "address": "西湖边",
                "lat": 30.252,
                "lng": 120.141,
                "rating": 4.8,
                "image_url": "https://example.com/placeholder.jpg",
                "source": "amap",
            },
            {
                "id": "food-quality",
                "name": "西湖楼外楼",
                "type": "餐饮服务;中餐厅",
                "address": "孤山路",
                "lat": 30.253,
                "lng": 120.142,
                "rating": 4.8,
                "image_url": "http://aos-comment.amap.com/louwailou.jpg",
                "source": "amap",
            },
        ]

        with patch("app.trip_planning.tool_executor._search_many", return_value=[]):
            result = TripPlanningToolbox().search_foods(
                {
                    "city": "杭州",
                    "attraction_candidates": [{"id": "poi-west-lake", "name": "西湖", "lat": 30.25, "lng": 120.14, "source": "amap"}],
                    "hotel_options": [],
                    "recommendations": [],
                },
                {},
            )

        self.assertEqual(result["food_candidates"][0]["name"], "西湖楼外楼")
        details = result["recommendations"][0]["item_details"][0]
        self.assertEqual(details["name"], "西湖楼外楼")
        self.assertEqual(details["image_url"], "https://aos-comment.amap.com/louwailou.jpg")
        self.assertEqual(details["image_source_id"], "food-quality")
        self.assertEqual(details["image_source_name"], "西湖楼外楼")

    def test_finalized_activity_restores_verified_poi_image(self):
        plan = [{"activities": [{"title": "游览西湖", "location": "西湖", "image": "https://example.com/wrong.jpg"}]}]
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
        self.assertEqual(activity["image_source_id"], "poi-west-lake")
        self.assertEqual(activity["image_source_name"], "西湖")

    def test_unverified_activity_image_is_removed(self):
        plan = [{"activities": [{"title": "神秘景点", "location": "不存在景点", "image": "https://example.com/random.jpg"}]}]
        state = {
            "city": "杭州",
            "attraction_candidates": [],
            "food_candidates": [],
            "hotel_options": [],
        }

        result = _enrich_plan_media(plan, state)

        self.assertNotIn("image", result[0]["activities"][0])

    def test_duplicate_finalizer_locations_are_replaced_with_unused_verified_pois(self):
        plan = [
            {"day": 1, "activities": [{"title": "游览西湖", "type": "景点游览", "location": "西湖"}]},
            {"day": 2, "activities": [{"title": "再游西湖", "type": "景点游览", "location": "西湖"}]},
        ]
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
                },
                {
                    "id": "poi-lingyin",
                    "name": "灵隐寺",
                    "lat": 30.24,
                    "lng": 120.10,
                    "image_url": "https://store.is.autonavi.com/lingyin.jpg",
                    "source": "amap",
                },
            ],
            "food_candidates": [],
            "hotel_options": [],
        }

        result = _enrich_plan_media(plan, state)
        locations = [
            activity["location"]
            for day in result
            for activity in day["activities"]
        ]

        self.assertEqual(locations, ["西湖", "灵隐寺"])
        self.assertEqual(result[1]["activities"][0]["image"], "https://store.is.autonavi.com/lingyin.jpg")
        self.assertEqual(result[1]["activities"][0]["source_id"], "poi-lingyin")

    def test_duplicate_restaurant_is_replaced_with_restaurant(self):
        plan = [
            {"activities": [{"title": "午餐", "type": "美食餐饮", "location": "楼外楼"}]},
            {"activities": [{"title": "晚餐", "type": "美食餐饮", "location": "楼外楼"}]},
        ]
        state = {
            "city": "杭州",
            "attraction_candidates": [{"id": "attraction", "name": "灵隐寺", "lat": 30.24, "lng": 120.1, "source": "amap"}],
            "food_candidates": [
                {"id": "food-1", "name": "楼外楼", "lat": 30.25, "lng": 120.14, "source": "amap"},
                {"id": "food-2", "name": "知味观", "lat": 30.26, "lng": 120.15, "source": "amap"},
            ],
        }
        result = _enrich_plan_media(plan, state)
        self.assertEqual(result[1]["activities"][0]["location"], "知味观")

    def test_fallback_itinerary_does_not_repeat_attractions_across_days(self):
        state = {
            "city": "杭州",
            "days": 3,
            "attraction_candidates": [
                {"id": "poi-west-lake", "name": "西湖", "lat": 30.25, "lng": 120.14, "source": "amap"},
                {"id": "poi-lingyin", "name": "灵隐寺", "lat": 30.24, "lng": 120.10, "source": "amap"},
            ],
            "food_candidates": [],
            "hotel_options": [],
        }

        plan = _fallback_itinerary(state)
        attraction_locations = [
            activity["location"]
            for day in plan
            for activity in day["activities"]
            if activity["type"] == "景点游览"
        ]

        self.assertEqual(attraction_locations, ["西湖", "灵隐寺"])

    def test_external_images_are_upgraded_to_https(self):
        self.assertEqual(
            normalize_image_url("http://aos-comment.amap.com/example.jpg"),
            "https://aos-comment.amap.com/example.jpg",
        )
        self.assertEqual(normalize_image_url("javascript:alert(1)"), "")


if __name__ == "__main__":
    unittest.main()
