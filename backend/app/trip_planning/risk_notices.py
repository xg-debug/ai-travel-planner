from __future__ import annotations

from typing import Any, Dict, List


class TripRiskNoticeService:
    def build_notices(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        notices: List[Dict[str, Any]] = []
        notices.extend(self._weather_notices(state))
        notices.extend(self._budget_notices(state))
        notices.extend(self._price_reference_notices(state))
        notices.extend(self._opening_hour_notices(state))
        notices.extend(self._review_notices(state))
        return notices

    def _weather_notices(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for impact in state.get("weather_impacts", []) or []:
            if impact.get("condition_type") in {"normal", "good"}:
                continue
            result.append(
                {
                    "type": "weather",
                    "level": impact.get("severity", "medium"),
                    "title": "天气影响提醒",
                    "content": impact.get("advice", "天气可能影响部分户外活动，请出行前再次确认。"),
                    "related_day": impact.get("day"),
                    "related_place": "",
                }
            )
        return result

    def _budget_notices(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        budget = state.get("estimated_budget", {}) or {}
        requested = float(state.get("budget_amount") or 0)
        total = float(budget.get("total") or 0)
        if not requested or total <= requested:
            return []
        return [
            {
                "type": "budget",
                "level": "medium",
                "title": "预算超出提醒",
                "content": f"当前估算总预算约 {int(total)} 元，高于你输入的 {int(requested)} 元，建议减少高消费餐饮或调整住宿标准。",
                "related_day": None,
                "related_place": "",
            }
        ]

    def _opening_hour_notices(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        notices: List[Dict[str, Any]] = []
        for day in state.get("plan", []) or []:
            day_no = day.get("day")
            for activity in day.get("activities", []) or []:
                if activity.get("opening_hours"):
                    continue
                text = " ".join(str(activity.get(key, "") or "") for key in ("title", "type", "location"))
                if any(marker in text for marker in ("博物", "馆", "展", "景区", "公园")):
                    notices.append(
                        {
                            "type": "opening_hours",
                            "level": "low",
                            "title": "开放时间提醒",
                            "content": f"{activity.get('location') or activity.get('title')} 的开放时间可能变化，建议出行前确认。",
                            "related_day": day_no,
                            "related_place": activity.get("location", ""),
                        }
                    )
        return notices[:5]

    def _price_reference_notices(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        has_reference_price = False
        for day in state.get("plan", []) or []:
            hotel = day.get("hotel_recommendation") or {}
            if hotel.get("price_is_estimated") or hotel.get("price_estimate"):
                has_reference_price = True
                break
            for activity in day.get("activities", []) or []:
                if activity.get("price_note") or activity.get("price_confidence") == "reference":
                    has_reference_price = True
                    break
            if has_reference_price:
                break
        if not has_reference_price:
            return []
        return [
            {
                "type": "price_reference",
                "level": "low",
                "title": "价格参考提醒",
                "content": "门票、人均餐饮和酒店价格会随日期、库存和平台活动变化，当前预算仅作规划参考。",
                "related_day": None,
                "related_place": "",
            }
        ]

    def _review_notices(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        notices: List[Dict[str, Any]] = []
        for issue in state.get("review_issues", []) or []:
            notices.append(
                {
                    "type": issue.get("type", "review"),
                    "level": "medium" if issue.get("severity") == "major" else "low",
                    "title": "行程质量提醒",
                    "content": issue.get("message", ""),
                    "related_day": issue.get("day"),
                    "related_place": "",
                }
            )
        return notices[:5]


risk_notice_service = TripRiskNoticeService()


def risk_notice_node(state: Dict[str, Any]) -> Dict[str, Any]:
    notices = risk_notice_service.build_notices(state)
    return {"risk_notices": notices}
