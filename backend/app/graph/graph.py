from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class TripPlanner:
    """简化的旅行规划器"""
    
    def __init__(self):
        from app.graph.nodes import (
            validation_node,
            planner_node,
            poi_node,
            weather_node,
            recommendation_node,
            budget_node,
            summary_node
        )
        self.nodes = {
            "validate": validation_node,
            "planner": planner_node,
            "poi": poi_node,
            "weather": weather_node,
            "recommendations": recommendation_node,
            "budget": budget_node,
            "summary": summary_node
        }
    
    def plan_trip(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行旅行规划流程"""
        logger.info("Starting trip planning process")
        
        try:
            # 1. 验证输入
            state = self.nodes["validate"](state)
            
            # 2. 规划行程
            state.update(self.nodes["planner"](state))
            
            # 3. 获取POI信息
            state.update(self.nodes["poi"](state))
            
            # 4. 获取天气信息
            state.update(self.nodes["weather"](state))
            
            # 5. 生成推荐
            state.update(self.nodes["recommendations"](state))
            
            # 6. 估算预算
            state.update(self.nodes["budget"](state))
            
            # 7. 生成总结
            state.update(self.nodes["summary"](state))
            
            logger.info("Trip planning completed successfully")
            return state
            
        except Exception as e:
            logger.error(f"Error in trip planning: {e}")
            # 返回基本结果
            return {
                "final_output": f"行程规划失败: {str(e)}",
                "poi_data": {},
                "plan": [],
                "weather_data": {},
                "recommendations": [],
                "estimated_budget": {}
            }

# 创建规划器实例
trip_planner = TripPlanner()

# 兼容旧接口
class MockGraph:
    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return trip_planner.plan_trip(state)

app_trip_graph = MockGraph()