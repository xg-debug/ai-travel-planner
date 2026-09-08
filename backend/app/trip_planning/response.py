from typing import Any, Dict

from app.models.trip_schemas import TripResponse
from app.trip_planning.recommendations import dedupe_recommendations


def build_trip_response(result: Dict[str, Any]) -> TripResponse:
    return TripResponse(
        plan=result.get("final_output", ""),
        planning_warnings=result.get("planning_warnings") or [],
        pois=result.get("poi_data", {}),
        itinerary=result.get("plan"),
        weather=result.get("weather_data"),
        recommendations=dedupe_recommendations(result.get("recommendations") or [], result.get("city", "")),
        hotels=result.get("hotel_options"),
        estimated_budget=result.get("estimated_budget"),
        daily_budgets=result.get("daily_budgets"),
        risk_notices=result.get("risk_notices"),
        weather_impacts=result.get("weather_impacts"),
        quality_score=result.get("quality_score"),
        intercity_transport=result.get("intercity_transport") or (result.get("transport_plan") or {}).get("intercity_transport"),
    )
