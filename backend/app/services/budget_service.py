import logging
from typing import List, Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class BudgetService:
    """预算估算服务"""
    
    def __init__(self):
        # 预算水平基准（每人每天，单位：元）
        self.budget_levels = {
            "经济": {
                "accommodation": 150,
                "food": 100,
                "transportation": 50,
                "tickets": 50,
                "shopping": 50
            },
            "中等": {
                "accommodation": 300,
                "food": 150,
                "transportation": 100,
                "tickets": 100,
                "shopping": 100
            },
            "豪华": {
                "accommodation": 800,
                "food": 300,
                "transportation": 200,
                "tickets": 200,
                "shopping": 200
            }
        }
        
        # 活动类型成本系数
        self.activity_cost_factors = {
            "观光": 1.0,
            "文化": 1.2,
            "美食": 1.5,
            "购物": 2.0,
            "娱乐": 1.8,
            "户外": 1.3,
            "休闲": 1.1,
            "交通": 0.8
        }
    
    def estimate_budget(
        self, 
        itinerary: List[Dict[str, Any]], 
        travelers: int = 1,
        budget_level: str = "中等"
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
        
        # 计算总天数（在try块外定义，确保在except块中可用）
        days = len(itinerary) if itinerary else 1
        
        try:
            # 获取基准预算
            base_budget = self.budget_levels.get(budget_level, self.budget_levels["中等"])
            
            # 计算各项费用
            breakdown = {}
            total = 0
            
            for category, daily_cost in base_budget.items():
                category_total = daily_cost * days * travelers
                breakdown[category] = category_total
                total += category_total
            
            # 根据活动类型调整预算
            activity_adjustment = self._calculate_activity_adjustment(itinerary)
            total *= activity_adjustment
            
            # 调整各项费用比例
            for category in breakdown:
                breakdown[category] = int(breakdown[category] * activity_adjustment)
            
            # 生成预算报告
            budget_report = {
                "total": int(total),
                "per_person": int(total / travelers) if travelers > 0 else int(total),
                "per_day": int(total / days) if days > 0 else int(total),
                "breakdown": breakdown,
                "currency": "CNY",
                "budget_level": budget_level,
                "travelers": travelers,
                "days": days,
                "activity_adjustment": round(activity_adjustment, 2),
                "tips": self._get_budget_tips(budget_level, itinerary)
            }
            
            logger.info(f"Budget estimated: {budget_report['total']} CNY")
            return budget_report
            
        except Exception as e:
            logger.error(f"Error estimating budget: {e}")
            return self._get_fallback_budget(days, travelers, budget_level)
    
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
    
    def _get_fallback_budget(self, days: int, travelers: int, budget_level: str) -> Dict[str, Any]:
        """获取回退预算（当计算失败时）"""
        base_cost = {
            "经济": 300,
            "中等": 500,
            "豪华": 1000
        }.get(budget_level, 500)
        
        total = base_cost * days * travelers
        
        breakdown = {
            "accommodation": int(total * 0.4),
            "food": int(total * 0.3),
            "transportation": int(total * 0.15),
            "tickets": int(total * 0.1),
            "shopping": int(total * 0.05)
        }
        
        return {
            "total": total,
            "per_person": base_cost * days,
            "per_day": base_cost * travelers,
            "breakdown": breakdown,
            "currency": "CNY",
            "budget_level": budget_level,
            "travelers": travelers,
            "days": days,
            "activity_adjustment": 1.0,
            "tips": [
                "此为估算费用，实际花费可能有所不同",
                "建议根据实际情况调整预算"
            ]
        }
    
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

# 创建服务实例
budget_service = BudgetService()

# 导出函数
def estimate_budget(
    itinerary: List[Dict[str, Any]], 
    travelers: int = 1,
    budget_level: str = "中等"
) -> Dict[str, Any]:
    return budget_service.estimate_budget(itinerary, travelers, budget_level)

def optimize_budget(
    budget: Dict[str, Any], 
    constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return budget_service.optimize_budget(budget, constraints)