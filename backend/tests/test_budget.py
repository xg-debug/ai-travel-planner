import unittest

from app.trip_planning.budget import estimate_budget


class BudgetTests(unittest.TestCase):
    def test_three_day_trip_charges_two_hotel_nights(self):
        days = [{"day": index + 1, "hotel_recommendation": {"budget_price_per_room": 400}, "activities": []}
                for index in range(3)]
        result = estimate_budget(days, travelers=2)
        self.assertEqual(result["breakdown"]["accommodation"], 800)
        self.assertEqual([day["categories"]["accommodation"] for day in result["daily_budgets"]], [400, 400, 0])
        for category, amount in result["breakdown"].items():
            self.assertEqual(amount, sum(day["categories"][category] for day in result["daily_budgets"]))
        self.assertEqual(result["total"], sum(day["total"] for day in result["daily_budgets"]))

    def test_intercity_total_is_allocated_to_daily_budget(self):
        result = estimate_budget(
            [{"day": 1, "activities": []}], travelers=1,
            intercity_transport={"total_cost": 500, "outbound": {"total_cost": 200}, "inbound": {"total_cost": 200}},
        )
        self.assertEqual(result["breakdown"]["transportation"], result["daily_budgets"][0]["categories"]["transportation"])


if __name__ == "__main__":
    unittest.main()
