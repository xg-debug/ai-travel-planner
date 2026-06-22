import logging
from typing import List, Dict, Any, Optional

from app.trip_planning.constants import ACTIVITY_COST_FACTORS, BUDGET_LEVELS

logger = logging.getLogger(__name__)


class BudgetService:
    def __init__(self):
        self.budget_levels = BUDGET_LEVELS
        self.activity_cost_factors = ACTIVITY_COST_FACTORS
    
    def estimate_budget(
        self, 
        itinerary: List[Dict[str, Any]], 
        travelers: int = 1,
        budget_level: str = "中等",
        target_total: Optional[float] = None,
        intercity_transport: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        估算旅行预算
        
        Args:
            itinerary: 行程安排
            travelers: 旅行人数
            budget_level: 预算水平（经济、中等、豪华）
            
        Returns:
            预算估算结果
        """
        logger.info(f"Estimating budget for {len(itinerary)} days, {travelers} travelers, {budget_level} level")
        
        days = len(itinerary) if itinerary else 1

        base_budget = self.budget_levels.get(budget_level, self.budget_levels["中等"])
        breakdown = self._calculate_breakdown_from_itinerary(itinerary, travelers, base_budget)
        daily_budgets = self._calculate_daily_budgets(itinerary, travelers, base_budget)
        self._merge_intercity_transport_cost(breakdown, daily_budgets, intercity_transport)
        total = sum(int(value) for value in breakdown.values())
        activity_adjustment = self._calculate_activity_adjustment(itinerary)
        
        budget_report = {
            "total": int(total),
            "per_person": int(total / travelers) if travelers > 0 else int(total),
            "per_day": int(total / days) if days > 0 else int(total),
            "breakdown": breakdown,
            "daily_budgets": daily_budgets,
            "intercity_transport": intercity_transport or {},
            "currency": "CNY",
            "budget_level": budget_level,
            "travelers": travelers,
            "days": days,
            "activity_adjustment": round(activity_adjustment, 2),
            "tips": self._get_budget_tips(budget_level, itinerary)
        }
        if target_total:
            budget_report = self._annotate_target_budget(budget_report, float(target_total), travelers, days)
        
        logger.info(f"Budget estimated: {budget_report['total']} CNY")
        return budget_report

    def _annotate_target_budget(
        self,
        budget_report: Dict[str, Any],
        target_total: float,
        travelers: int,
        days: int,
    ) -> Dict[str, Any]:
        requested_total = int(target_total)
        if requested_total <= 0:
            return budget_report

        current_total = int(budget_report.get("total") or 0)
        target_min_total = int(requested_total * 0.85)
        budget_report["requested_total"] = requested_total
        budget_report["target_min_total"] = target_min_total
        budget_report["is_over_budget"] = current_total > requested_total
        budget_report["is_under_budget"] = current_total < target_min_total
        budget_report["remaining_budget"] = max(0, requested_total - current_total)
        budget_report["budget_alignment"] = {
            "status": "over_budget" if current_total > requested_total else "within_budget",
            "estimated_total": current_total,
            "requested_total": requested_total,
            "target_min_total": target_min_total,
            "remaining_budget": max(0, requested_total - current_total),
        }
        return budget_report

    def _distribute_gap(self, categories: Dict[str, Any], gap: int, weights: Dict[str, float]) -> None:
        if gap <= 0:
            return
        remaining = int(gap)
        keys = list(weights.keys())
        for key in keys[:-1]:
            addition = int(round(gap * weights[key]))
            categories[key] = int(categories.get(key) or 0) + addition
            remaining -= addition
        last_key = keys[-1]
        categories[last_key] = int(categories.get(last_key) or 0) + max(0, remaining)

    def _safe_number(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            if isinstance(value, (int, float)):
                return float(value)
            import re
            matched = re.search(r"\d+(?:\.\d+)?", str(value))
            return float(matched.group()) if matched else 0.0
        except Exception:
            return 0.0

    def _get_activity_category(self, activity: Dict[str, Any]) -> str:
        text = " ".join(
            [
                str(activity.get("title", "")),
                str(activity.get("type", "")),
                str(activity.get("description", "")),
                str(activity.get("location", "")),
            ]
        )
        if any(token in text for token in ("早餐", "午餐", "晚餐", "餐", "美食", "小吃", "咖啡", "茶")):
            return "food"
        if any(token in text for token in ("地铁", "打车", "公交", "交通", "通勤", "车程")):
            return "transportation"
        if any(token in text for token in ("购物", "商圈", "步行街", "伴手礼")):
            return "shopping"
        return "tickets"

    def _calculate_breakdown_from_itinerary(
        self,
        itinerary: List[Dict[str, Any]],
        travelers: int,
        base_budget: Dict[str, int],
    ) -> Dict[str, int]:
        days = len(itinerary) if itinerary else 1
        breakdown = {
            "accommodation": 0.0,
            "food": 0.0,
            "transportation": 0.0,
            "tickets": 0.0,
            "shopping": 0.0,
        }

        for day in itinerary:
            hotel = day.get("hotel_recommendation") or day.get("hotel") or {}
            hotel_price = self._hotel_budget_price(hotel)
            breakdown["accommodation"] += self._hotel_total_for_day(hotel_price, travelers, base_budget)

            for activity in day.get("activities", []) or []:
                if activity.get("is_intercity_transport"):
                    continue
                category = self._get_activity_category(activity)
                explicit_cost = self._activity_total_cost(activity, category, travelers)
                ticket_price = self._safe_number(activity.get("ticket_price") or activity.get("ticketPrice"))
                if category == "food":
                    breakdown["food"] += explicit_cost or float(base_budget["food"])
                elif category == "transportation":
                    breakdown["transportation"] += explicit_cost or float(base_budget["transportation"]) * 0.5
                elif category == "shopping":
                    breakdown["shopping"] += explicit_cost or float(base_budget["shopping"]) * 0.3
                else:
                    breakdown["tickets"] += ticket_price * max(travelers, 1) if ticket_price > 0 else explicit_cost

        if breakdown["food"] <= 0:
            breakdown["food"] = float(base_budget["food"]) * travelers * days
        if breakdown["transportation"] <= 0:
            breakdown["transportation"] = float(base_budget["transportation"]) * travelers * max(days - 1, 1)
        if breakdown["tickets"] <= 0:
            breakdown["tickets"] = float(base_budget["tickets"]) * travelers * days * 0.7
        if breakdown["shopping"] <= 0:
            breakdown["shopping"] = float(base_budget["shopping"]) * travelers * days * 0.4

        return {key: int(round(value)) for key, value in breakdown.items()}

    def _calculate_daily_budgets(
        self,
        itinerary: List[Dict[str, Any]],
        travelers: int,
        base_budget: Dict[str, int],
    ) -> List[Dict[str, Any]]:
        daily: List[Dict[str, Any]] = []
        for index, day in enumerate(itinerary or []):
            categories = {
                "accommodation": 0.0,
                "food": 0.0,
                "transportation": 0.0,
                "tickets": 0.0,
                "shopping": 0.0,
            }
            hotel = day.get("hotel_recommendation") or day.get("hotel") or {}
            hotel_price = self._hotel_budget_price(hotel)
            categories["accommodation"] = self._hotel_total_for_day(hotel_price, travelers, base_budget)

            for activity in day.get("activities", []) or []:
                if activity.get("is_intercity_transport"):
                    continue
                category = self._get_activity_category(activity)
                explicit_cost = self._activity_total_cost(activity, category, travelers)
                ticket_price = self._safe_number(activity.get("ticket_price") or activity.get("ticketPrice"))
                if category == "food":
                    categories["food"] += explicit_cost or float(base_budget["food"])
                elif category == "transportation":
                    categories["transportation"] += explicit_cost or float(base_budget["transportation"]) * 0.5
                elif category == "shopping":
                    categories["shopping"] += explicit_cost or float(base_budget["shopping"]) * 0.3
                else:
                    categories["tickets"] += ticket_price * max(travelers, 1) if ticket_price > 0 else explicit_cost

            if categories["food"] <= 0:
                categories["food"] = float(base_budget["food"]) * travelers
            if categories["transportation"] <= 0:
                categories["transportation"] = float(base_budget["transportation"]) * travelers
            if categories["tickets"] <= 0:
                categories["tickets"] = float(base_budget["tickets"]) * travelers * 0.7
            if categories["shopping"] <= 0:
                categories["shopping"] = float(base_budget["shopping"]) * travelers * 0.2

            rounded = {key: int(round(value)) for key, value in categories.items()}
            daily.append(
                {
                    "day": int(day.get("day") or index + 1),
                    "date": day.get("date"),
                    "total": sum(rounded.values()),
                    "categories": rounded,
                    "risk": "normal",
                }
            )
        return daily

    def _hotel_total_for_day(self, hotel_price: float, travelers: int, base_budget: Dict[str, int]) -> float:
        rooms = max(1, (max(int(travelers or 1), 1) + 1) // 2)
        if hotel_price > 0:
            return hotel_price * rooms
        return float(base_budget["accommodation"]) * travelers

    def _activity_total_cost(self, activity: Dict[str, Any], category: str, travelers: int) -> float:
        explicit = self._safe_number(activity.get("cost_estimate") or activity.get("cost"))
        if explicit > 0:
            return explicit
        avg_cost = self._safe_number(activity.get("avg_cost") or activity.get("avgCost"))
        if avg_cost > 0 and category == "food":
            return avg_cost * max(travelers, 1)
        return 0.0

    def _hotel_budget_price(self, hotel: Dict[str, Any]) -> float:
        if not hotel:
            return 0.0
        explicit = self._safe_number(hotel.get("budget_price_per_room") or hotel.get("budgetPricePerRoom"))
        if explicit > 0:
            return explicit
        if hotel.get("price_is_estimated") or hotel.get("priceIsEstimated"):
            return 0.0
        return self._safe_number(hotel.get("price_estimate") or hotel.get("priceEstimate") or hotel.get("price"))

    def _merge_intercity_transport_cost(
        self,
        breakdown: Dict[str, int | float],
        daily_budgets: List[Dict[str, Any]],
        intercity_transport: Optional[Dict[str, Any]],
    ) -> None:
        if not intercity_transport:
            return

        outbound = intercity_transport.get("outbound") or {}
        inbound = intercity_transport.get("inbound") or {}
        outbound_cost = int(self._safe_number(outbound.get("total_cost")))
        inbound_cost = int(self._safe_number(inbound.get("total_cost")))
        total_cost = int(self._safe_number(intercity_transport.get("total_cost"))) or outbound_cost + inbound_cost
        if total_cost <= 0:
            return

        breakdown["transportation"] = int(breakdown.get("transportation") or 0) + total_cost
        if not daily_budgets:
            return

        if outbound_cost > 0:
            self._add_daily_transport_cost(daily_budgets[0], outbound_cost, "intercity_outbound")
        if inbound_cost > 0:
            self._add_daily_transport_cost(daily_budgets[-1], inbound_cost, "intercity_inbound")

    def _add_daily_transport_cost(self, daily_budget: Dict[str, Any], cost: int, risk: str) -> None:
        categories = dict(daily_budget.get("categories") or {})
        categories["transportation"] = int(categories.get("transportation") or 0) + cost
        daily_budget["categories"] = categories
        daily_budget["total"] = int(sum(int(value) for value in categories.values()))
        daily_budget["risk"] = risk if daily_budget.get("risk") == "normal" else daily_budget.get("risk", risk)
    
    def _calculate_activity_adjustment(self, itinerary: List[Dict[str, Any]]) -> float:
        """根据活动类型计算预算调整系数"""
        if not itinerary:
            return 1.0
        
        total_factor = 0
        activity_count = 0
        
        for day in itinerary:
            activities = day.get('activities', [])
            for activity in activities:
                activity_type = activity.get('type', '观光')
                factor = self.activity_cost_factors.get(activity_type, 1.0)
                total_factor += factor
                activity_count += 1
        
        if activity_count == 0:
            return 1.0
        
        avg_factor = total_factor / activity_count
        # 调整范围：0.8 - 1.5
        return max(0.8, min(1.5, avg_factor))
    
    def _get_budget_tips(self, budget_level: str, itinerary: List[Dict[str, Any]]) -> List[str]:
        """获取预算建议"""
        tips = []
        
        # 通用建议
        tips.append("以下为估算费用，实际花费可能因季节、个人消费习惯等因素有所不同")
        tips.append("门票、人均餐饮和住宿价格均为参考，实时价格可能波动，请以官方渠道或预订平台为准")
        tips.append("建议预留10-20%的应急资金")
        
        # 根据预算水平提供建议
        if budget_level == "经济":
            tips.append("经济型旅行建议：选择公共交通、经济型酒店、当地小吃")
            tips.append("可以关注景点优惠门票和免费开放日")
        elif budget_level == "中等":
            tips.append("中等预算建议：平衡舒适度和性价比，适当体验当地特色")
            tips.append("可以考虑套餐优惠和提前预订折扣")
        elif budget_level == "豪华":
            tips.append("豪华型旅行建议：优先考虑舒适度和体验质量")
            tips.append("可以预订高端酒店、特色餐厅和私人导游服务")
        
        # 根据活动类型提供建议
        activity_types = set()
        for day in itinerary:
            for activity in day.get('activities', []):
                activity_type = activity.get('type')
                if activity_type:
                    activity_types.add(activity_type)
        
        if "购物" in activity_types:
            tips.append("购物预算建议：制定购物清单，避免冲动消费")
        
        if "美食" in activity_types:
            tips.append("美食预算建议：尝试当地特色小吃，性价比更高")
        
        if "文化" in activity_types:
            tips.append("文化体验建议：部分博物馆有免费开放日，可提前查询")
        
        return tips
    
    def optimize_budget(
        self, 
        budget: Dict[str, Any], 
        constraints: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        优化预算分配
        
        Args:
            budget: 原始预算
            constraints: 约束条件（如最大总预算、特定类别限制等）
            
        Returns:
            优化后的预算
        """
        logger.info("Optimizing budget allocation")
        
        try:
            optimized = budget.copy()
            total = budget.get("total", 0)
            breakdown = budget.get("breakdown", {}).copy()
            
            # 应用约束条件
            if constraints:
                max_total = constraints.get("max_total")
                if max_total and total > max_total:
                    # 按比例缩减各项费用
                    scale = max_total / total
                    for category in breakdown:
                        breakdown[category] = int(breakdown[category] * scale)
                    total = max_total
                
                # 特定类别约束
                for category, limit in constraints.get("category_limits", {}).items():
                    if category in breakdown and breakdown[category] > limit:
                        breakdown[category] = limit
            
            optimized["total"] = total
            optimized["breakdown"] = breakdown
            optimized["per_person"] = int(total / budget.get("travelers", 1))
            optimized["per_day"] = int(total / budget.get("days", 1))
            
            # 添加优化建议
            optimized["optimization_tips"] = self._get_optimization_tips(budget, optimized)
            
            logger.info(f"Budget optimized: {optimized['total']} CNY (saved {budget['total'] - optimized['total']} CNY)")
            return optimized
            
        except Exception as e:
            logger.error(f"Error optimizing budget: {e}")
            return budget
    
    def _get_optimization_tips(
        self, 
        original: Dict[str, Any], 
        optimized: Dict[str, Any]
    ) -> List[str]:
        """获取优化建议"""
        tips = []
        
        original_total = original.get("total", 0)
        optimized_total = optimized.get("total", 0)
        
        if optimized_total < original_total:
            savings = original_total - optimized_total
            savings_percent = (savings / original_total) * 100
            tips.append(f"通过优化，节省了{savings}元（{savings_percent:.1f}%）")
        
        # 分析各项费用
        original_breakdown = original.get("breakdown", {})
        optimized_breakdown = optimized.get("breakdown", {})
        
        for category in optimized_breakdown:
            original_val = original_breakdown.get(category, 0)
            optimized_val = optimized_breakdown.get(category, 0)
            
            if optimized_val < original_val:
                reduction = original_val - optimized_val
                tips.append(f"{category}费用减少{reduction}元")
        
        # 通用优化建议
        tips.append("优化建议：")
        tips.append("1. 提前预订住宿和交通，通常有折扣")
        tips.append("2. 选择当地特色小吃，性价比更高")
        tips.append("3. 使用公共交通代替出租车")
        tips.append("4. 关注景点优惠门票和免费开放日")
        tips.append("5. 制定购物预算，避免冲动消费")
        
        return tips

def budget_node(state: Dict[str, Any]) -> Dict[str, Any]:
    plan = state.get("plan", [])
    travelers = state.get("travelers", 1)
    budget_level = state.get("budget", "中等")
    intercity_transport = state.get("intercity_transport") or (state.get("transport_plan") or {}).get("intercity_transport") or {}
    estimated_budget = budget_service.estimate_budget(plan, travelers, budget_level, state.get("budget_amount") or None, intercity_transport)
    if state.get("budget_amount"):
        estimated_budget["requested_total"] = int(float(state.get("budget_amount") or 0))
        estimated_budget["is_over_budget"] = int(estimated_budget.get("total") or 0) > estimated_budget["requested_total"]
    daily_budgets = estimated_budget.get("daily_budgets", [])
    enriched_plan = []
    for index, day in enumerate(plan or []):
        next_day = dict(day)
        if index < len(daily_budgets):
            next_day["budget"] = daily_budgets[index]
        enriched_plan.append(next_day)
    return {"plan": enriched_plan or plan, "estimated_budget": estimated_budget, "daily_budgets": daily_budgets, "intercity_transport": intercity_transport}


budget_service = BudgetService()

# 导出函数
def estimate_budget(
    itinerary: List[Dict[str, Any]], 
    travelers: int = 1,
    budget_level: str = "中等",
    target_total: Optional[float] = None,
    intercity_transport: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return budget_service.estimate_budget(itinerary, travelers, budget_level, target_total, intercity_transport)

def optimize_budget(
    budget: Dict[str, Any], 
    constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return budget_service.optimize_budget(budget, constraints)
