from typing import Dict, Any
import logging
from langgraph.graph import END, StateGraph

from app.agents import (
    hotel_search_agent_node,
    planning_agent_node,
    poi_detail_agent_node,
    query_agent_node,
    scenic_search_agent_node,
)
from app.graph.nodes import budget_node, summary_node, weather_tool_step
from app.graph.state import TripState

logger = logging.getLogger(__name__)

def build_trip_graph():
    workflow = StateGraph(TripState)
    workflow.add_node("query_agent", query_agent_node)
    workflow.add_node("scenic_agent", scenic_search_agent_node)
    workflow.add_node("hotel_agent", hotel_search_agent_node)
    workflow.add_node("planning_agent", planning_agent_node)
    workflow.add_node("poi_agent", poi_detail_agent_node)
    workflow.add_node("weather_tool", weather_tool_step)
    workflow.add_node("budget", budget_node)
    workflow.add_node("summary", summary_node)

    workflow.set_entry_point("query_agent")
    workflow.add_edge("query_agent", "scenic_agent")
    workflow.add_edge("scenic_agent", "hotel_agent")
    workflow.add_edge("hotel_agent", "planning_agent")
    workflow.add_edge("planning_agent", "poi_agent")
    workflow.add_edge("poi_agent", "weather_tool")
    workflow.add_edge("weather_tool", "budget")
    workflow.add_edge("budget", "summary")
    workflow.add_edge("summary", END)

    return workflow.compile()


class TripPlanner:
    """旅行规划器。"""

    def __init__(self):
        self.graph = build_trip_graph()

    def plan_trip(self, state: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Starting trip planning process")
        return self.graph.invoke(state)


trip_planner = TripPlanner()
app_trip_graph = trip_planner.graph
