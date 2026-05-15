from __future__ import annotations

from typing import Any, Dict, List


RAIN_MARKERS = ("雨", "雷", "阵雨", "暴雨")
SNOW_MARKERS = ("雪",)
FOG_MARKERS = ("雾", "霾")
OUTDOOR_MARKERS = ("公园", "海", "山", "湾", "湖", "河", "风景", "户外", "沙滩", "步道", "广场")
INDOOR_MARKERS = ("博物", "美术", "展", "馆", "商场", "购物", "餐", "咖啡", "书店")


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

            if any(marker in text for marker in RAIN_MARKERS):
                condition_type = "rain"
                severity = "medium"
                outdoor_penalty = 30
                indoor_boost = 20
                advice = "当天可能有雨，建议减少海边、公园、登山等长时间户外活动，优先安排室内展馆、商场或餐饮体验。"
            elif any(marker in text for marker in SNOW_MARKERS):
                condition_type = "snow"
                severity = "medium"
                outdoor_penalty = 25
                indoor_boost = 15
                advice = "当天可能有雪，建议减少长时间户外停留，并预留交通时间。"
            elif any(marker in text for marker in FOG_MARKERS):
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
        is_outdoor = any(marker in text for marker in OUTDOOR_MARKERS)
        is_indoor = any(marker in text for marker in INDOOR_MARKERS)
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
