from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


ORCHESTRATOR_ACTIONS = {
    "plan_search_strategy",
    "get_weather",
    "search_attractions",
    "search_foods",
    "search_hotels",
    "score_candidates",
    "evaluate_transport",
    "enrich_poi",
    "review_itinerary",
    "estimate_budget",
    "build_risk_notices",
    "finalize",
}


class OrchestratorAction(BaseModel):
    thought: str = Field(default="")
    action: str
    args: Dict[str, Any] = Field(default_factory=dict)
    final: Optional[Dict[str, Any]] = None


class ToolObservation(BaseModel):
    step: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)


class FinalPlanModel(BaseModel):
    itinerary: List[Dict[str, Any]] = Field(default_factory=list)
    final_output: str = ""
