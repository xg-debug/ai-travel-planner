import logging
from typing import List, Dict, Any, Optional
from app.core.llm import recommendation_llm
from app.core.config import settings
import json

logger = logging.getLogger(__name__)

class RecommendationService:
    """个性化推荐服务"""
    
    def __init__(self):
        self.recommendation_categories = {
            "culture": ["博物馆", "历史遗迹", "艺术馆", "文化街区"],
            "food": ["特色餐厅", "小吃街", "美食市场", "咖啡馆"],
            "nature": ["公园", "山景", "湖景", "海滩"],
            "shopping": ["商场", "市场", "特色店铺", "免税店"],
            "adventure": ["徒步路线", "水上活动", "极限运动", "探险项目"],
            "relax": ["温泉", "SPA", "瑜伽馆", "休闲公园"],
            "family": ["儿童乐园", "动物园", "科技馆", "亲子活动"],
            "photography": ["观景台", "网红打卡点", "夜景", "特色建筑"]
        }
    
    def get_recommendations(
        self, 
        city: str, 
        preferences: List[str], 
        plan: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取个性化推荐
        
        Args:
            city: 城市名称
            preferences: 用户偏好列表
            plan: 现有行程计划
            
        Returns:
            推荐列表
        """
        logger.info(f"Getting recommendations for {city} with preferences: {preferences}")

        # 默认走规则推荐，避免额外 LLM 延迟；需要时可通过环境变量开启 LLM 推荐增强。
        if not settings.ENABLE_LLM_RECOMMENDATION:
            return self._get_rule_based_recommendations(city, preferences, plan)

        try:
            # 使用LLM生成智能推荐
            prompt = self._build_recommendation_prompt(city, preferences, plan)
            response = recommendation_llm.invoke(prompt)
            
            try:
                recommendations = json.loads(response.content)
                if isinstance(recommendations, list):
                    return recommendations
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM response as JSON, using fallback")
            
            # 回退到基于规则的推荐
            return self._get_rule_based_recommendations(city, preferences, plan)
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return self._get_fallback_recommendations(city, preferences)
    
    def _build_recommendation_prompt(
        self, 
        city: str, 
        preferences: List[str], 
        plan: Optional[List[Dict[str, Any]]]
    ) -> str:
        """构建推荐提示词"""
        plan_text = ""
        if plan:
            plan_text = "现有行程计划：\n"
            for day in plan[:3]:  # 只取前3天作为参考
                plan_text += f"第{day.get('day', 1)}天："
                activities = day.get('activities', [])
                if activities:
                    plan_text += f"{activities[0].get('title', '')}等{len(activities)}个活动\n"
                else:
                    plan_text += "暂无安排\n"
        
        prompt = f"""
        你是一个旅行推荐专家，请为前往{city}的旅行者提供个性化推荐。
        
        旅行者偏好：{', '.join(preferences) if preferences else '无特殊偏好'}
        
        {plan_text}
        
        请根据以下要求生成推荐：
        1. 针对每个偏好类别，推荐2-3个具体地点或活动
        2. 每个推荐包含：名称、类型、简要描述、推荐理由
        3. 考虑地点的评分、价格、适合时间等因素
        4. 避免与现有行程重复（如果提供了行程）
        5. 提供实用建议和小贴士
        
        输出格式为JSON数组：
        [
            {{
                "type": "推荐类别",
                "title": "推荐标题",
                "items": ["地点1", "地点2", "地点3"],
                "description": "推荐描述",
                "reasoning": "推荐理由",
                "best_time": "最佳时间",
                "price_range": "价格范围",
                "tips": "实用建议"
            }}
        ]
        
        请确保推荐内容实用、具体，符合旅行者的偏好。
        """
        
        return prompt
    
    def _get_rule_based_recommendations(
        self, 
        city: str, 
        preferences: List[str], 
        plan: Optional[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """基于规则的推荐"""
        recommendations = []
        
        # 如果没有偏好，提供通用推荐
        if not preferences:
            preferences = ["culture", "food", "nature"]
        
        for pref in preferences[:3]:  # 最多3个偏好类别
            categories = self.recommendation_categories.get(pref, ["景点"])
            
            recommendation = {
                "type": self._translate_preference(pref),
                "title": f"{city}{self._translate_preference(pref)}推荐",
                "items": [f"{city}{cat}" for cat in categories[:3]],
                "description": f"基于您的{self._translate_preference(pref)}偏好，我们推荐以下地点",
                "reasoning": "这些地点评分高，符合您的偏好，且交通便利",
                "best_time": "全天" if pref in ["shopping", "food"] else "上午",
                "price_range": "免费-中等" if pref in ["nature", "culture"] else "中等-高端",
                "tips": self._get_recommendation_tips(pref)
            }
            recommendations.append(recommendation)
        
        return recommendations
    
    def _get_fallback_recommendations(self, city: str, preferences: List[str]) -> List[Dict[str, Any]]:
        """回退推荐（当所有方法都失败时）"""
        return [
            {
                "type": "美食",
                "title": f"{city}美食推荐",
                "items": [f"{city}特色餐厅", f"{city}小吃街", f"{city}美食市场"],
                "description": "品尝当地特色美食是旅行的重要部分",
                "reasoning": "这些地点提供正宗当地美食，评分较高",
                "best_time": "午餐和晚餐时间",
                "price_range": "中等",
                "tips": "建议尝试当地特色菜，注意餐厅营业时间"
            },
            {
                "type": "文化",
                "title": f"{city}文化体验",
                "items": [f"{city}博物馆", f"{city}历史遗迹", f"{city}艺术馆"],
                "description": "了解当地文化和历史",
                "reasoning": "这些地点展示当地文化特色，具有教育意义",
                "best_time": "上午",
                "price_range": "免费-中等",
                "tips": "部分场馆需要提前预约，注意开放时间"
            },
            {
                "type": "购物",
                "title": f"{city}购物推荐",
                "items": [f"{city}商场", f"{city}特色市场", f"{city}商业街"],
                "description": "购买纪念品和当地特产",
                "reasoning": "这些地点商品丰富，价格合理",
                "best_time": "下午",
                "price_range": "各种价位",
                "tips": "可以适当讲价，注意商品质量"
            }
        ]
    
    def _translate_preference(self, pref: str) -> str:
        """翻译偏好类别"""
        translations = {
            "culture": "文化",
            "food": "美食",
            "nature": "自然",
            "shopping": "购物",
            "adventure": "探险",
            "relax": "休闲",
            "family": "亲子",
            "photography": "摄影"
        }
        return translations.get(pref, pref)
    
    def _get_recommendation_tips(self, pref: str) -> str:
        """获取推荐小贴士"""
        tips = {
            "culture": "建议提前了解历史文化背景，穿着舒适的鞋子",
            "food": "尝试当地特色菜，注意食物卫生",
            "nature": "注意天气变化，准备合适的装备",
            "shopping": "比较价格，注意商品真伪",
            "adventure": "注意安全，遵守相关规定",
            "relax": "提前预约，注意营业时间",
            "family": "选择适合儿童的活动，注意安全",
            "photography": "选择合适的光线时间，注意拍摄规定"
        }
        return tips.get(pref, "请提前查询最新信息")

# 创建服务实例
recommendation_service = RecommendationService()

# 导出函数
def get_recommendations(
    city: str, 
    preferences: List[str], 
    plan: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    return recommendation_service.get_recommendations(city, preferences, plan)
