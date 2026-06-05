from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

from app.agents.shared import dedupe
from app.services.weather_impact_service import weather_impact_service


PREFERENCE_KEYWORDS = {
    "classic": ("经典", "地标", "景点", "公园", "广场", "古城", "名胜"),
    "food": ("餐", "美食", "小吃", "咖啡", "茶", "夜市", "老字号"),
    "local": ("本地", "小众", "街区", "社区", "市集"),
    "photo": ("拍照", "摄影", "夜景", "海", "湾", "公园", "观景"),
    "shopping": ("购物", "商场", "商圈", "步行街", "市集"),
    "citywalk": ("街区", "步行街", "公园", "广场", "citywalk", "历史街区"),
    "nature": ("自然", "公园", "海", "湾", "山", "湖", "风景", "绿道"),
    "art": ("艺术", "美术", "展", "馆", "剧场", "文化"),
    "history": ("历史", "古", "博物", "纪念", "遗址", "文化"),
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        matched = re.search(r"\d+(?:\.\d+)?", str(value))
        return float(matched.group()) if matched else default
    except Exception:
        return default


def _text(item: Dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key, "") or "")
        for key in ("name", "type", "address", "description", "opening_hours")
    )


def _normalize_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


class ScoringService:
    def score_attractions(self, candidates: Sequence[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._score_candidates(candidates, context, kind="attraction")

    def score_foods(self, candidates: Sequence[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._score_candidates(candidates, context, kind="food")

    def score_hotels(self, candidates: Sequence[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return self._score_candidates(candidates, context, kind="hotel")

    def _score_candidates(self, candidates: Sequence[Dict[str, Any]], context: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
        weather_impacts = list(context.get("weather_impacts", []) or [])
        primary_impact = weather_impacts[0] if weather_impacts else {}
        scored: List[Dict[str, Any]] = []
        for item in candidates:
            candidate = dict(item)
            factors = self._score_factors(candidate, context, kind, primary_impact)
            if kind == "attraction":
                weights = {"preference": 0.30, "route": 0.25, "poi_quality": 0.20, "weather": 0.15, "budget": 0.10}
            elif kind == "food":
                weights = {"local_feature": 0.30, "route": 0.25, "poi_quality": 0.20, "budget": 0.15, "preference": 0.10}
            else:
                weights = {"location": 0.35, "budget": 0.25, "poi_quality": 0.20, "route_connection": 0.15, "preference": 0.05}
            total = sum(factors.get(key, 0.0) * weight for key, weight in weights.items())
            candidate["score"] = _normalize_score(total)
            candidate["score_factors"] = {key: _normalize_score(value) for key, value in factors.items()}
            candidate["reason_tags"] = self._reason_tags(candidate, kind)
            candidate["reason"] = self.build_reason(candidate, kind)
            scored.append(candidate)
        scored.sort(key=lambda value: float(value.get("score", 0) or 0), reverse=True)
        return scored

    def _score_factors(self, item: Dict[str, Any], context: Dict[str, Any], kind: str, weather_impact: Dict[str, Any]) -> Dict[str, float]:
        if kind == "food":
            return {
                "local_feature": self._local_feature_score(item),
                "route": self._route_score(item, context),
                "poi_quality": self._poi_quality_score(item),
                "budget": self._budget_score(item, context, kind),
                "preference": self._preference_score(item, context),
            }
        if kind == "hotel":
            return {
                "location": self._hotel_location_score(item),
                "budget": self._budget_score(item, context, kind),
                "poi_quality": self._poi_quality_score(item),
                "route_connection": self._route_score(item, context),
                "preference": self._preference_score(item, context),
            }
        return {
            "preference": self._preference_score(item, context),
            "route": self._route_score(item, context),
            "poi_quality": self._poi_quality_score(item),
            "weather": weather_impact_service.score_candidate_weather_fit(item, weather_impact),
            "budget": self._budget_score(item, context, kind),
        }

    def _preference_score(self, item: Dict[str, Any], context: Dict[str, Any]) -> float:
        preferences = list(context.get("preferences", []) or [])
        if not preferences:
            return 75.0
        text = _text(item).lower()
        hits = 0
        for pref in preferences:
            keywords = PREFERENCE_KEYWORDS.get(str(pref), ())
            if any(keyword.lower() in text for keyword in keywords):
                hits += 1
        return 55.0 + min(hits, 3) * 15.0

    def _route_score(self, item: Dict[str, Any], context: Dict[str, Any]) -> float:
        if item.get("lat") not in (None, "", 0, 0.0) and item.get("lng") not in (None, "", 0, 0.0):
            return 82.0
        return 55.0

    def _poi_quality_score(self, item: Dict[str, Any]) -> float:
        score = 55.0
        rating = _safe_float(item.get("rating"), 0.0)
        if rating > 0:
            score += min(rating, 5.0) * 7.0
        if item.get("id"):
            score += 5
        if item.get("address"):
            score += 5
        if item.get("lat") not in (None, "", 0, 0.0) and item.get("lng") not in (None, "", 0, 0.0):
            score += 8
        if item.get("opening_hours"):
            score += 4
        return score

    def _budget_score(self, item: Dict[str, Any], context: Dict[str, Any], kind: str) -> float:
        price = _safe_float(item.get("price"), 0.0)
        budget_level = str(context.get("budget") or "中等")
        target_total = _safe_float(context.get("budget_amount"), 0.0)
        travelers = max(int(context.get("travelers") or 1), 1)
        days = max(int(context.get("days") or 1), 1)
        target_per_person_day = target_total / travelers / days if target_total > 0 else 0
        if price <= 0:
            return 82.0
        if kind == "hotel":
            if target_per_person_day >= 900:
                return 92.0 if price >= 500 else 68.0
            if target_per_person_day >= 550:
                return 92.0 if 250 <= price <= 900 else 70.0
            if budget_level == "经济":
                return 90.0 if price <= 350 else 55.0
            if budget_level == "豪华":
                return 88.0 if price >= 500 else 72.0
            return 90.0 if price <= 800 else 65.0
        if kind == "food" and target_per_person_day >= 900:
            return 90.0 if 100 <= price <= 500 else 72.0
        if kind == "food" and target_per_person_day >= 550:
            return 90.0 if 60 <= price <= 300 else 74.0
        if budget_level == "经济":
            return 90.0 if price <= 80 else 60.0
        if budget_level == "豪华":
            return 82.0
        return 90.0 if price <= 200 else 70.0

    def _local_feature_score(self, item: Dict[str, Any]) -> float:
        text = _text(item)
        score = 65.0
        if any(marker in text for marker in ("本地", "特色", "老字号", "小吃", "夜市", "风味")):
            score += 25
        if any(marker in text for marker in ("连锁", "分店")):
            score -= 8
        return score

    def _hotel_location_score(self, item: Dict[str, Any]) -> float:
        text = _text(item)
        score = 70.0
        if any(marker in text for marker in ("地铁", "中心", "商圈", "交通", "火车站", "机场")):
            score += 18
        if item.get("lat") not in (None, "", 0, 0.0) and item.get("lng") not in (None, "", 0, 0.0):
            score += 8
        return score

    def _reason_tags(self, item: Dict[str, Any], kind: str) -> List[str]:
        factors = item.get("score_factors", {}) or {}
        sorted_keys = sorted(factors.keys(), key=lambda key: float(factors.get(key, 0) or 0), reverse=True)
        mapping = {
            "preference": "符合旅行偏好",
            "route": "适合顺路安排",
            "route_connection": "便于衔接每日路线",
            "poi_quality": "地点信息较完整",
            "weather": "天气适配度较高",
            "budget": "预算匹配度较好",
            "local_feature": "本地特色明显",
            "location": "位置便利",
        }
        return dedupe([mapping.get(key, key) for key in sorted_keys[:3]])

    def build_reason(self, item: Dict[str, Any], kind: str) -> str:
        name = str(item.get("name", "") or "该地点")
        tags = item.get("reason_tags", []) or []
        if not tags:
            return f"{name}来自真实地点查询结果，适合纳入本次行程。"
        category = "住宿" if kind == "hotel" else ("餐饮" if kind == "food" else "景点")
        return f"推荐{name}作为{category}候选，因为" + "、".join(tags[:3]) + "。"


scoring_service = ScoringService()
