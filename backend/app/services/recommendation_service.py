import logging
from typing import Any, Dict, List, Optional

from app.domain import travel_domain_service


logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Real recommendation service.

    Data is derived only from real provider results:
    - POI search
    - restaurant-like POI search
    - hotel search
    """

    DEFAULT_PREFERENCES = ["culture", "food", "nature"]

    QUERY_PRESETS: Dict[str, Dict[str, Any]] = {
        "culture": {
            "type": "文化",
            "title": "文化景点推荐",
            "queries": ["博物馆", "历史街区", "文化地标"],
            "best_time": "上午到下午",
            "price_range": "免费-中等",
            "tips": "优先查看开放时间和预约要求。",
            "source": "poi",
        },
        "food": {
            "type": "美食",
            "title": "本地餐饮推荐",
            "queries": ["本地特色餐厅", "老字号", "小吃"],
            "best_time": "午餐和晚餐",
            "price_range": "中等",
            "tips": "建议错峰用餐，并优先选择评分较高的餐饮点。",
            "source": "poi",
        },
        "nature": {
            "type": "自然",
            "title": "自然风景推荐",
            "queries": ["城市公园", "风景区", "湖景公园"],
            "best_time": "上午",
            "price_range": "免费-中等",
            "tips": "注意天气变化，户外行程建议避开极端天气。",
            "source": "poi",
        },
        "shopping": {
            "type": "购物",
            "title": "购物休闲推荐",
            "queries": ["商圈", "步行街", "特色市场"],
            "best_time": "下午到晚间",
            "price_range": "各种价位",
            "tips": "建议优先选择交通方便、可步行串联的区域。",
            "source": "poi",
        },
        "photography": {
            "type": "摄影",
            "title": "拍照打卡推荐",
            "queries": ["观景台", "夜景地标", "特色建筑"],
            "best_time": "傍晚到夜间",
            "price_range": "免费-中等",
            "tips": "建议结合日落或夜景时段前往。",
            "source": "poi",
        },
        "family": {
            "type": "亲子",
            "title": "亲子游玩推荐",
            "queries": ["动物园", "科技馆", "儿童乐园"],
            "best_time": "白天",
            "price_range": "中等",
            "tips": "建议优先选择步行压力较小、停留时间灵活的地点。",
            "source": "poi",
        },
        "hotel": {
            "type": "酒店",
            "title": "住宿推荐",
            "queries": ["市中心酒店", "高评分酒店", "交通便利酒店"],
            "best_time": "全天",
            "price_range": "",
            "tips": "建议结合预算和行程中心区选择住宿。",
            "source": "hotel",
        },
    }

    PREFERENCE_ALIASES = {
        "culture": "culture",
        "food": "food",
        "nature": "nature",
        "shopping": "shopping",
        "photography": "photography",
        "family": "family",
        "hotel": "hotel",
        "住宿": "hotel",
        "酒店": "hotel",
        "文化": "culture",
        "人文": "culture",
        "历史": "culture",
        "美食": "food",
        "餐饮": "food",
        "自然": "nature",
        "户外": "nature",
        "购物": "shopping",
        "拍照": "photography",
        "摄影": "photography",
        "亲子": "family",
    }

    def get_recommendations(
        self,
        city: str,
        preferences: List[str],
        plan: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("Getting real recommendations for city=%s preferences=%s", city, preferences)
        normalized_preferences = self._normalize_preferences(preferences)
        recommendations: List[Dict[str, Any]] = []

        for pref in normalized_preferences:
            preset = self.QUERY_PRESETS.get(pref)
            if not preset:
                continue

            candidates = self._search_candidates(city, preset)
            if not candidates:
                logger.info("No real candidates found for city=%s pref=%s", city, pref)
                continue

            unique_candidates = self._dedupe_candidates(candidates)
            items = [item["name"] for item in unique_candidates[:5] if item.get("name")]
            if not items:
                continue

            recommendations.append(
                {
                    "type": preset["type"],
                    "title": f"{city}{preset['title']}",
                    "items": items,
                    "description": self._build_description(city, preset["type"], unique_candidates[:3]),
                    "reasoning": self._build_reasoning(unique_candidates[:3]),
                    "best_time": preset["best_time"],
                    "price_range": self._build_price_range(unique_candidates[:3], preset["price_range"]),
                    "tips": preset["tips"],
                }
            )

        if plan:
            derived = self._derive_from_plan(plan)
            for item in derived:
                if not any(existing["type"] == item["type"] for existing in recommendations):
                    recommendations.append(item)

        return recommendations

    def _normalize_preferences(self, preferences: List[str]) -> List[str]:
        normalized: List[str] = []
        raw_list = preferences or self.DEFAULT_PREFERENCES
        for item in raw_list:
            text = str(item or "").strip().lower()
            if not text:
                continue
            mapped = self.PREFERENCE_ALIASES.get(text, text)
            if mapped not in normalized and mapped in self.QUERY_PRESETS:
                normalized.append(mapped)

        if not normalized:
            normalized = list(self.DEFAULT_PREFERENCES)

        if "hotel" not in normalized:
            normalized.append("hotel")
        return normalized[:4]

    def _search_candidates(self, city: str, preset: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for query in preset["queries"]:
            try:
                if preset["source"] == "hotel":
                    items = travel_domain_service.search_hotels(query, city, 1, 8)
                else:
                    items = travel_domain_service.search_pois(query, city, 1, 8)
                results.extend(items or [])
            except Exception as exc:
                logger.warning("Recommendation search failed city=%s query=%s error=%s", city, query, exc)
        return results

    def _dedupe_candidates(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        best_by_name: Dict[str, Dict[str, Any]] = {}
        for item in items:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            current = best_by_name.get(name)
            if not current or self._score(item) > self._score(current):
                best_by_name[name] = item
        return sorted(best_by_name.values(), key=self._score, reverse=True)

    def _score(self, item: Dict[str, Any]) -> float:
        rating = float(item.get("rating", 0) or 0)
        bonus = 0.0
        if item.get("image_url"):
            bonus += 0.4
        if item.get("address"):
            bonus += 0.2
        price = str(item.get("price", "")).strip()
        if price:
            bonus += 0.1
        return rating + bonus

    def _build_description(self, city: str, category: str, items: List[Dict[str, Any]]) -> str:
        names = [str(item.get("name", "")).strip() for item in items if item.get("name")]
        if not names:
            return f"基于真实搜索结果整理出的{category}推荐。"
        return f"基于{city}的真实搜索结果，优先筛出了 {', '.join(names[:3])} 等更值得优先考虑的{category}地点。"

    def _build_reasoning(self, items: List[Dict[str, Any]]) -> str:
        parts = []
        for item in items:
            name = str(item.get("name", "")).strip()
            rating = item.get("rating")
            address = str(item.get("address", "")).strip()
            if not name:
                continue
            detail = name
            if rating:
                detail += f" 评分约 {rating}"
            if address:
                detail += f"，位于 {address}"
            parts.append(detail)
        return "；".join(parts) if parts else "基于真实查询结果筛选。"

    def _build_price_range(self, items: List[Dict[str, Any]], default: str) -> str:
        prices = [str(item.get("price", "")).strip() for item in items if str(item.get("price", "")).strip()]
        meaningful = [price for price in prices if price]
        if meaningful:
            return " / ".join(meaningful[:2])
        return default

    def _derive_from_plan(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[str]] = {
            "景点": [],
            "餐饮": [],
            "酒店": [],
        }

        for day in plan:
            hotel = day.get("hotel_recommendation") or day.get("hotel") or {}
            hotel_name = str(hotel.get("name", "")).strip()
            if hotel_name and hotel_name not in grouped["酒店"]:
                grouped["酒店"].append(hotel_name)

            for activity in day.get("activities", []) or []:
                name = str(activity.get("location") or activity.get("title") or "").strip()
                if not name:
                    continue
                text = " ".join(
                    [
                        str(activity.get("title", "")),
                        str(activity.get("type", "")),
                        str(activity.get("description", "")),
                        str(activity.get("location", "")),
                    ]
                )
                bucket = "餐饮" if any(token in text for token in ("早餐", "午餐", "晚餐", "餐", "美食", "小吃", "咖啡")) else "景点"
                if name not in grouped[bucket]:
                    grouped[bucket].append(name)

        recommendations: List[Dict[str, Any]] = []
        for category, items in grouped.items():
            if not items:
                continue
            recommendations.append(
                {
                    "type": category,
                    "title": f"{category}推荐",
                    "items": items[:5],
                    "description": f"基于当前真实行程整理出的{category}候选。",
                    "reasoning": "仅保留当前行程中已经出现的真实地点，不生成虚构推荐。",
                    "best_time": "",
                    "price_range": "",
                    "tips": "",
                }
            )
        return recommendations


recommendation_service = RecommendationService()


def get_recommendations(
    city: str,
    preferences: List[str],
    plan: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    return recommendation_service.get_recommendations(city, preferences, plan)
