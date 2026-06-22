from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict


WorkflowDecision = Literal["continue", "replan", "final"]


class TripPlanningGraphState(TypedDict, total=False):
    query: str
    city: str
    departure_city: str
    days: int
    preferences: List[str]
    accommodation_preference: str
    budget: str
    budget_amount: float
    travelers: int
    start_date: str
    outbound_departure_datetime: str
    return_arrival_datetime: str

    planning_brief: Dict[str, Any]
    action_plan: Dict[str, Any]
    next_actions: List[Dict[str, Any]]
    executed_actions: List[str]
    tool_results: Dict[str, Any]
    replan_request: str
    replanner_decision: WorkflowDecision
    replanner_reason: str
    iteration: int
    max_iterations: int

    weather_data: Dict[str, Any]
    weather_impacts: List[Dict[str, Any]]
    attraction_candidates: List[Dict[str, Any]]
    food_candidates: List[Dict[str, Any]]
    hotel_options: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    transport_plan: Dict[str, Any]
    intercity_transport: Dict[str, Any]

    plan: List[Dict[str, Any]]
    final_output: str
    estimated_budget: Dict[str, Any]
    daily_budgets: List[Dict[str, Any]]
    risk_notices: List[Dict[str, Any]]
    quality_score: Dict[str, Any]
