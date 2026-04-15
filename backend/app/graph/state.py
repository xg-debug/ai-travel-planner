from typing import List, Dict, Any, Optional, TypedDict
from pydantic import BaseModel

class TripState(TypedDict, total=False):
    query: str
    city: str
    days: int
    preferences: Optional[List[str]]
    budget: Optional[str]
    travelers: Optional[int]
    start_date: Optional[str]
    query_plan: Dict[str, Any]
    attraction_candidates: List[Dict[str, Any]]
    hotel_options: List[Dict[str, Any]]
    plan: List[Dict[str, Any]]
    poi_data: Dict[str, Any]
    weather_data: Dict[str, Any]
    recommendations: Optional[List[Dict[str, Any]]]
    estimated_budget: Optional[Dict[str, Any]]
    final_output: str

# Pydantic模型用于API请求/响应
class TripRequest(BaseModel):
    query: str
    city: str
    days: int
    preferences: Optional[List[str]] = None
    budget: Optional[str] = None
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
    humidity: float
    wind_speed: float
    icon: str
