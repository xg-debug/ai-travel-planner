from __future__ import annotations

from typing import Any, Dict, Generator

from app.trip_planning.agent_planner import plan_execute_replan_agent
from app.trip_planning.harness import TripPlanningHarness
from app.trip_planning.state import TripPlanningState


class TripPlanningWorkflow:
    """Compatibility facade around the observable planning harness."""

    def __init__(self) -> None:
        self._harness = TripPlanningHarness(plan_execute_replan_agent)

    def run(self, initial_state: TripPlanningState) -> TripPlanningState:
        return self._harness.run(self._initial_graph_state(initial_state))

    def stream(self, initial_state: TripPlanningState) -> Generator[Dict[str, Any], None, None]:
        yield from self._harness.stream(self._initial_graph_state(initial_state))

    def _initial_graph_state(self, state: TripPlanningState) -> Dict[str, Any]:
        return {
            **dict(state),
            "tool_results": {},
            "recommendations": [],
            "attraction_candidates": [],
            "food_candidates": [],
            "hotel_options": [],
            "weather_data": {},
            "weather_impacts": [],
            "plan": [],
        }

trip_planning_workflow = TripPlanningWorkflow()
