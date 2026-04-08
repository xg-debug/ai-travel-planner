import json
import logging
from typing import Dict, Any, List
from app.core.llm import planner_llm, summary_llm, recommendation_llm
from app.services.amap_service import search_pois, get_weather_forecast
from app.services.recommendation_service import get_recommendations
from app.services.budget_service import estimate_budget
from app.core.config import settings

logger = logging.getLogger(__name__)

def validation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """验证输入参数"""
    logger.info(f"Validating trip request: {state}")
    
    # 验证必填字段
    if not state.get('city'):
        raise ValueError("目的地城市不能为空")
    
    if not state.get('query'):
        raise ValueError("旅行需求不能为空")
    
    if not state.get('days') or state['days'] <= 0:
        raise ValueError("旅行天数必须大于0")
    
    # 验证天数限制
    if state['days'] > settings.MAX_TRIP_DAYS:
        raise ValueError(f"旅行天数不能超过{settings.MAX_TRIP_DAYS}天")
    
    # 设置默认值
    state.setdefault('preferences', [])
    state.setdefault('travelers', 1)
    state.setdefault('budget', '中等')
    
    logger.info(f"Validation passed: {state}")
    return state

def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """行程规划节点"""
    logger.info(f"Planning trip for {state['city']} ({state['days']} days)")
    
    # 构建更详细的提示词
    preferences_text = ', '.join(state.get('preferences', [])) if state.get('preferences') else '无特殊偏好'
    budget_level = state.get('budget', '中等')
    travelers = state.get('travelers', 1)
    
    prompt = f"""
    你是一个专业的旅行规划师，请根据以下需求为{travelers}位旅行者规划{state['days']}天的{state['city']}旅行行程：
    
    ## 旅行需求详情
    目的地：{state['city']}
    旅行天数：{state['days']}天
    旅行人数：{travelers}人
    预算水平：{budget_level}
    兴趣偏好：{preferences_text}
    具体需求：{state['query']}
    
    ## 规划要求
    1. 生成{state['days']}天的详细行程，每天包含4-6个主要活动
    2. 每个活动包含：时间、标题、详细描述、地点、预计时长、费用估算、实用建议
    3. 根据预算水平推荐合适的住宿、餐饮和交通方式
    4. 考虑景点开放时间、交通时间和休息时间
    5. 提供每日主题和整体行程逻辑
    
    ## 活动类型分类
    - 观光游览：景点参观、地标打卡
    - 文化体验：博物馆、历史遗迹、艺术展览
    - 美食餐饮：餐厅推荐、特色小吃、美食体验
    - 购物娱乐：购物中心、特色商店、娱乐活动
    - 户外活动：公园、徒步、自然景观
    - 休闲放松：SPA、咖啡馆、休闲活动
    
    ## 输出格式要求
    返回JSON数组，每个元素代表一天：
    [
        {{
            "day": 1,
            "date": "2024-01-01",
            "theme": "城市探索与文化体验",
            "summary": "今日行程概览",
            "activities": [
                {{
                    "time": "09:00-11:00",
                    "title": "参观故宫博物院",
                    "description": "探索中国古代皇宫建筑，了解明清历史",
                    "type": "文化体验",
                    "location": "故宫博物院",
                    "duration": 120,
                    "cost_estimate": 60,
                    "tips": "建议提前网上购票，避开周末人流高峰",
                    "transportation": "地铁1号线天安门东站"
                }}
            ],
            "meals": {{
                "breakfast": {{
                    "suggestion": "酒店早餐或当地特色早餐店",
                    "budget": "20-50元/人"
                }},
                "lunch": {{
                    "suggestion": "王府井小吃街",
                    "budget": "50-100元/人"
                }},
                "dinner": {{
                    "suggestion": "全聚德烤鸭店",
                    "budget": "150-200元/人"
                }}
            }},
            "accommodation": {{
                "suggestion": "王府井附近四星级酒店",
                "budget": "600-800元/晚",
                "features": ["交通便利", "靠近景点", "设施齐全"]
            }},
            "transportation_tips": "今日主要使用地铁和步行，建议购买交通卡",
            "weather_consideration": "户外活动建议携带防晒用品",
            "important_notes": "故宫周一闭馆，请合理安排时间"
        }}
    ]
    
    ## 特别注意事项
    1. 行程安排要合理，避免过于紧凑
    2. 考虑旅行者的体力和兴趣
    3. 提供实用的本地建议
    4. 根据预算水平调整推荐
    5. 确保信息准确可靠
    
    请生成专业、实用、个性化的旅行行程。
    """
    
    try:
        response = planner_llm.invoke(prompt)
        content = response.content
        
        # 确保内容是字符串
        if not isinstance(content, str):
            content = str(content)
        
        # 尝试解析JSON
        try:
            plan_data = json.loads(content)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\[.*\]|\{.*\}', content, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group())
            else:
                raise ValueError("LLM 返回内容无法解析为行程 JSON")
        
        # 验证计划数据
        if not isinstance(plan_data, list):
            raise ValueError("计划数据必须是数组")
        
        if len(plan_data) != state['days']:
            logger.warning(f"计划天数({len(plan_data)})与请求天数({state['days']})不匹配")
        
        logger.info(f"Generated plan with {len(plan_data)} days")
        return {"plan": plan_data}
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse plan JSON: {e}")
        raise
    except Exception as e:
        logger.error(f"Error in planner_node: {e}")
        raise

def poi_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """POI信息获取节点"""
    logger.info(f"Fetching POI data for {state['city']}")
    
    plan = state.get('plan', [])
    city = state['city']
    poi_data = {}
    
    for day in plan:
        for activity in day.get('activities', []):
            location = activity.get('location')
            if location and location not in poi_data:
                try:
                    # 搜索POI信息
                    pois = search_pois(location, city)
                    if pois:
                        poi_data[location] = pois[0]  # 取第一个结果
                except Exception as e:
                    logger.error(f"Error fetching POI for {location}: {e}")
                    continue
    
    logger.info(f"Fetched {len(poi_data)} POIs")
    return {"poi_data": poi_data}

def weather_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """天气信息获取节点"""
    logger.info(f"Fetching weather for {state['city']}")
    
    city = state['city']
    days = state['days']
    
    try:
        # 获取天气预报
        weather_data = get_weather_forecast(city, days)
    except Exception as e:
        logger.error(f"Error fetching weather: {e}")
        raise
    
    logger.info(f"Weather data fetched: {len(weather_data.get('forecast', []))} days")
    return {"weather_data": weather_data}

def recommendation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """个性化推荐节点"""
    logger.info(f"Generating recommendations for {state['city']}")
    
    city = state['city']
    preferences = state.get('preferences', [])
    plan = state.get('plan', [])
    
    try:
        # 获取推荐
        recommendations = get_recommendations(city, preferences, plan)
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        raise
    
    logger.info(f"Generated {len(recommendations)} recommendations")
    return {"recommendations": recommendations}

def budget_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """预算估算节点"""
    logger.info(f"Estimating budget for {state['days']} days trip")
    
    plan = state.get('plan', [])
    travelers = state.get('travelers', 1)
    budget_level = state.get('budget', '中等')
    
    try:
        # 估算预算
        estimated_budget = estimate_budget(plan, travelers, budget_level)
    except Exception as e:
        logger.error(f"Error estimating budget: {e}")
        raise
    
    logger.info(f"Estimated budget: {estimated_budget.get('total')} {estimated_budget.get('currency')}")
    return {"estimated_budget": estimated_budget}

def summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """行程总结节点"""
    logger.info("Generating final trip summary")
    
    prompt = f"""
    请根据以下信息生成一份完整的旅行计划总结：
    
    ## 旅行基本信息
    - 目的地：{state['city']}
    - 旅行天数：{state['days']}天
    - 旅行人数：{state.get('travelers', 1)}人
    - 预算水平：{state.get('budget', '中等')}
    - 旅行偏好：{', '.join(state.get('preferences', [])) if state.get('preferences') else '无特殊偏好'}
    
    ## 详细行程安排
    {json.dumps(state.get('plan', []), ensure_ascii=False, indent=2)}
    
    ## 景点信息
    {json.dumps(state.get('poi_data', {}), ensure_ascii=False, indent=2)}
    
    ## 天气预报
    {json.dumps(state.get('weather_data', {}), ensure_ascii=False, indent=2)}
    
    ## 个性化推荐
    {json.dumps(state.get('recommendations', []), ensure_ascii=False, indent=2)}
    
    ## 预算估算
    {json.dumps(state.get('estimated_budget', {}), ensure_ascii=False, indent=2)}
    
    请生成一份结构清晰、内容详实的旅行计划文档，包含：
    1. 行程概览
    2. 每日详细安排（时间、活动、地点、注意事项）
    3. 景点介绍和实用信息
    4. 天气情况和穿衣建议
    5. 预算分析和省钱技巧
    6. 个性化推荐
    7. 安全提示和紧急联系方式
    8. 当地文化和礼仪注意事项
    
    使用友好的语气，提供实用的建议，让旅行者能够轻松理解和执行这个计划。
    """
    
    try:
        response = summary_llm.invoke(prompt)
        final_output = response.content
        
        logger.info("Summary generated successfully")
        return {"final_output": final_output}
        
    except Exception as e:
        logger.error(f"Error in summary_node: {e}")
        # 生成基本总结
        basic_summary = f"""
        # {state['city']} {state['days']}天旅行计划
        
        ## 行程概览
        本次旅行共{state['days']}天，目的地为{state['city']}。
        
        ## 主要景点
        {', '.join(list(state.get('poi_data', {}).keys())[:5]) if state.get('poi_data') else '暂无景点信息'}
        
        ## 预算估算
        总预算约{state.get('estimated_budget', {}).get('total', 0)}元。
        
        ## 温馨提示
        请根据天气情况准备衣物，注意旅行安全。
        """
        return {"final_output": basic_summary}
