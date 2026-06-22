from __future__ import annotations

from typing import Any, Dict, List

from app.trip_planning.constants import (
    RE_INDOOR,
    RE_OUTDOOR,
    RE_RAIN,
    RE_SNOW,
    RE_FOG,
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if isinstance(value, dict):
            return _safe_int(value.get("avg") or value.get("max") or value.get("min"), default)
        return int(float(value))
    except Exception:
        return default


def _condition_text(forecast: Dict[str, Any]) -> str:
    return " ".join(
        str(forecast.get(key, "") or "")
        for key in ("condition", "day_condition", "night_condition", "icon")
    )


class WeatherImpactService:
    def build_impacts(self, weather_data: Dict[str, Any], start_date: str | None, days: int) -> List[Dict[str, Any]]:
        forecasts = list((weather_data or {}).get("forecast", []) or [])
        impacts: List[Dict[str, Any]] = []
        for index in range(max(days, 0)):
            forecast = forecasts[index] if index < len(forecasts) else {}
            text = _condition_text(forecast)
            temperature = forecast.get("temperature") or {}
            high = _safe_int(temperature.get("max") if isinstance(temperature, dict) else temperature, 0)
            wind_power = str(forecast.get("day_wind_power") or forecast.get("night_wind_power") or "")
            condition_type = "normal"
            severity = "low"
            outdoor_penalty = 0
            indoor_boost = 0
            advice = "天气整体适合常规城市游览。"

            if RE_RAIN.search(text):
                condition_type = "rain"
                severity = "medium"
                outdoor_penalty = 30
                indoor_boost = 20
                advice = "当天可能有雨，建议减少海边、公园、登山等长时间户外活动，优先安排室内展馆、商场或餐饮体验。"
            elif RE_SNOW.search(text):
                condition_type = "snow"
                severity = "medium"
                outdoor_penalty = 25
                indoor_boost = 15
                advice = "当天可能有雪，建议减少长时间户外停留，并预留交通时间。"
            elif RE_FOG.search(text):
                condition_type = "fog"
                severity = "medium"
                outdoor_penalty = 18
                indoor_boost = 10
                advice = "当天能见度或空气质量可能较差，建议减少观景和长距离户外活动。"
            elif high >= 32:
                condition_type = "hot"
                severity = "medium"
                outdoor_penalty = 20
                indoor_boost = 12
                advice = "当天气温较高，建议避开正午户外活动，将户外安排在上午或傍晚。"
            elif wind_power and any(token in wind_power for token in ("5", "6", "7", "8", "9")):
                condition_type = "wind"
                severity = "medium"
                outdoor_penalty = 15
                indoor_boost = 8
                advice = "当天风力可能偏大，海边和高处景点建议缩短停留。"
            elif "晴" in text or "多云" in text:
                condition_type = "good"
                severity = "low"
                outdoor_penalty = 0
                indoor_boost = 0
                advice = "天气适合户外游览，可优先安排自然风光、海边、公园和城市步行。"

            impacts.append(
                {
                    "day": index + 1,
                    "date": forecast.get("date", ""),
                    "condition_type": condition_type,
                    "severity": severity,
                    "outdoor_penalty": outdoor_penalty,
                    "indoor_boost": indoor_boost,
                    "advice": advice,
                }
            )
        return impacts

    def score_candidate_weather_fit(self, candidate: Dict[str, Any], impact: Dict[str, Any] | None) -> float:
        if not impact:
            return 80.0
        text = " ".join(
            str(candidate.get(key, "") or "")
            for key in ("name", "type", "address", "description")
        )
        score = 82.0
        is_outdoor = RE_OUTDOOR.search(text) is not None
        is_indoor = RE_INDOOR.search(text) is not None
        score -= float(impact.get("outdoor_penalty", 0) or 0) if is_outdoor else 0
        score += float(impact.get("indoor_boost", 0) or 0) if is_indoor else 0
        if impact.get("condition_type") == "good" and is_outdoor:
            score += 10
        return max(0.0, min(100.0, score))

    def build_weather_advice(self, day_index: int, weather_impacts: List[Dict[str, Any]]) -> str:
        if 0 <= day_index < len(weather_impacts):
            return str(weather_impacts[day_index].get("advice", "") or "")
        return "天气数据可能变化，出行前请再次确认。"


weather_impact_service = WeatherImpactService()


def weather_tool_step(state: Dict[str, Any]) -> Dict[str, Any]:
    from app.domain import travel_domain_service
    import logging
    logger = logging.getLogger(__name__)
    city = state["city"]
    days = state["days"]
    try:
        weather_data = travel_domain_service.get_weather(city, days)
    except Exception as exc:
        logger.warning("Weather fetch failed city=%s error=%s", city, exc)
        weather_data = {
            "city": city,
            "report_time": "",
            "forecast": [
                {"date": "", "condition": "未知", "day_condition": "未知", "night_condition": "未知",
                 "temperature": {"min": 0, "max": 0, "avg": 0}, "humidity": 0, "wind_speed": 0, "icon": "unknown"}
                for _ in range(days)
            ],
        }
    weather_impacts_result = weather_impact_service.build_impacts(weather_data, state.get("start_date"), days)
    return {"weather_data": weather_data, "weather_impacts": weather_impacts_result}
