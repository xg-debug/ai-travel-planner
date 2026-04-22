from typing import List, Optional

from pydantic import BaseModel, Field


class PlannerOutput(BaseModel):
    travel_style: str = Field(min_length=1, max_length=80)
    planning_focus: str = Field(min_length=1, max_length=160)
    attraction_queries: List[str] = Field(default_factory=list, min_length=1, max_length=8)
    food_queries: List[str] = Field(default_factory=list, min_length=1, max_length=8)
    hotel_queries: List[str] = Field(default_factory=list, min_length=1, max_length=6)
    must_have: List[str] = Field(default_factory=list, max_length=8)


class HotelRecommendationModel(BaseModel):
    name: str = ""
    price_estimate: str | int | float | None = None
    address: str = ""
    reason: str = ""


class ItineraryActivityModel(BaseModel):
    time: str = ""
    title: str = ""
    description: str = ""
    type: str = ""
    location: str = ""
    duration: int = 90
    cost_estimate: int | float = 0
    ticket_price: int | float = 0
    tips: str = ""
    transportation: str = ""
    image: Optional[str] = None


class ItineraryDayModel(BaseModel):
    day: int
    date: Optional[str] = None
    theme: str = ""
    summary: str = ""
    hotel_recommendation: Optional[HotelRecommendationModel] = None
    activities: List[ItineraryActivityModel] = Field(default_factory=list, max_length=6)


class ReviewIssueModel(BaseModel):
    type: str
    severity: str
    day: Optional[int] = None
    message: str


class ReflectionContextModel(BaseModel):
    action: str
    summary: str
    issues: List[ReviewIssueModel] = Field(default_factory=list)


class ReflectionHistoryEntryModel(BaseModel):
    summary: str
    issue_count: int = 0
    post_patch_issue_count: int = 0
    patch_actions: List[dict] = Field(default_factory=list)
    rerun_required: bool = False
