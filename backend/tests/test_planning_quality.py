import unittest

from app.trip_planning.quality import audit_plan


def place(name, poi_id, kind, lat, lng):
    return {"title": name, "location": name, "type": kind, "source": "amap", "source_id": poi_id,
            "coordinates": {"lat": lat, "lng": lng}}


class PlanningQualityTests(unittest.TestCase):
    def test_complete_plan_passes_source_and_structure_checks(self):
        state = {
            "city": "杭州", "days": 2,
            "attraction_candidates": [
                {"id": "west-lake", "name": "西湖"}, {"id": "lingyin", "name": "灵隐寺"},
            ],
            "food_candidates": [
                {"id": "louwailou", "name": "楼外楼"}, {"id": "zhiweiguan", "name": "知味观"},
            ],
            "hotel_options": [{"id": "hotel-1", "name": "西湖酒店"}],
            "plan": [
                {"activities": [place("西湖", "west-lake", "景点游览", 30.25, 120.14),
                                place("楼外楼", "louwailou", "美食餐饮", 30.26, 120.15)],
                 "hotel_recommendation": {"source": "amap", "source_id": "hotel-1", "coordinates": {"lat": 30.24, "lng": 120.14}},
                 "map_route": {"legs": [{"ok": True}], "partial": False}},
                {"activities": [place("灵隐寺", "lingyin", "景点游览", 30.23, 120.10),
                                place("知味观", "zhiweiguan", "美食餐饮", 30.24, 120.11)],
                 "map_route": {"legs": [{"ok": True}], "partial": False}},
            ],
            "estimated_budget": {"total": 1200, "breakdown": {"food": 400, "accommodation": 800}},
            "daily_budgets": [{"total": 700}, {"total": 500}],
        }
        result = audit_plan(state)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["verified_poi_count"], 4)
        self.assertEqual(result["issues"], [])

    def test_unmatched_poi_and_unchecked_route_are_disclosed(self):
        state = {
            "city": "杭州", "days": 1,
            "attraction_candidates": [{"id": "real", "name": "西湖"}],
            "plan": [{"activities": [
                place("虚构景点", "invented", "景点游览", 30.25, 120.14),
                place("虚构景点", "invented", "景点游览", 30.25, 120.14),
            ], "map_route": {"legs": [{"ok": False}], "partial": True}}],
            "estimated_budget": {"total": 0, "breakdown": {}},
            "daily_budgets": [{"total": 0}],
        }
        result = audit_plan(state)
        self.assertEqual(result["verified_poi_count"], 0)
        self.assertLess(result["score"], 60)
        self.assertTrue(any("地图候选" in issue for issue in result["issues"]))
        self.assertTrue(any("路线" in issue for issue in result["issues"]))
        self.assertTrue(any("重复" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
