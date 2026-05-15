from typing import List, Dict, Any, Optional, TypedDict
from pydantic import BaseModel

class TripState(TypedDict, total=False):
    query: str
    city: str
    days: int
    preferences: Optional[List[str]]
    budget: Optional[str]
    budget_amount: Optional[float]
    travelers: Optional[int]
    start_date: Optional[str]
    query_plan: Dict[str, Any]
    execution_plan: Dict[str, Any]
    tasks: List[Dict[str, Any]]
    task_results: Dict[str, Any]
    completed_tasks: List[str]
    current_task: Optional[Dict[str, Any]]
    attraction_candidates: List[Dict[str, Any]]
    food_candidates: List[Dict[str, Any]]
    hotel_options: List[Dict[str, Any]]
    transport_plan: Dict[str, Any]
    draft_plan: List[Dict[str, Any]]
    reviewed_plan: List[Dict[str, Any]]
    review_issues: List[Dict[str, Any]]
    reflection_context: Dict[str, Any]
    reflection_history: List[Dict[str, Any]]
    plan: List[Dict[str, Any]]
    poi_data: Dict[str, Any]
    weather_data: Dict[str, Any]
    weather_impacts: List[Dict[str, Any]]
    recommendations: Optional[List[Dict[str, Any]]]
    estimated_budget: Optional[Dict[str, Any]]
    daily_budgets: Optional[List[Dict[str, Any]]]
    risk_notices: Optional[List[Dict[str, Any]]]
    scored_attractions: Optional[List[Dict[str, Any]]]
    scored_foods: Optional[List[Dict[str, Any]]]
    scored_hotels: Optional[List[Dict[str, Any]]]
    final_output: str

# Pydantic模型用于API请求/响应
class TripRequest(BaseModel):
    query: str
    city: str
    days: int
    preferences: Optional[List[str]] = None
    budget: Optional[str] = None
    budget_amount: Optional[float] = None
    travelers: Optional[int] = 1
    start_date: Optional[str] = None

class TripResponse(BaseModel):
    plan: str
    pois: Dict[str, Any]
    itinerary: Optional[List[Dict[str, Any]]] = None
    weather: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    hotels: Optional[List[Dict[str, Any]]] = None
    estimated_budget: Optional[Dict[str, Any]] = None
    daily_budgets: Optional[List[Dict[str, Any]]] = None
    risk_notices: Optional[List[Dict[str, Any]]] = None
    weather_impacts: Optional[List[Dict[str, Any]]] = None
    quality_score: Optional[Dict[str, Any]] = None

class PoiDetails(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    address: str
    type: str
    rating: float
    price: str
    description: str
    opening_hours: str
    best_time: str
    tips: str
    image_url: Optional[str] = None

class WeatherInfo(BaseModel):
    city: str
    date: str
    temperature: float
    condition: str
    day_condition: Optional[str] = None
    night_condition: Optional[str] = None
    humidity: float
    wind_speed: float
    day_wind_direction: Optional[str] = None
    night_wind_direction: Optional[str] = None
    day_wind_power: Optional[str] = None
    night_wind_power: Optional[str] = None
    icon: str
