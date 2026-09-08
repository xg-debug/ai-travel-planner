from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class TripPlanningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    departureCity: Optional[str] = None
    destination: str
    startDate: str
    endDate: str
    departureTime: str = "08:00"
    returnArrivalTime: str = "20:00"
    days: int
    travelers: int = 1
    interests: List[str] = Field(default_factory=list)
    budgetAmount: float = 0
    accommodationPreference: Literal["budget", "mid-range", "luxury"] = "mid-range"
    additionalRequirements: Optional[str] = None


class TripResponse(BaseModel):
    plan: str
    planning_warnings: List[str] = Field(default_factory=list)
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
    intercity_transport: Optional[Dict[str, Any]] = None


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
