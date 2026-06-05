from __future__ import annotations

from typing import Any, Dict, List

from app.agents.planner.planner_agent import build_baseline_query_plan
from app.agents.planner.planner_prompt import build_planner_prompt
from app.agents.reviewer.reviewer_agent import reviewer_agent_node
from app.agents.schemas import PlannerOutput
from app.agents.shared import dedupe, extract_json_block
from app.agents.workers.attraction_agent import attraction_search_agent_node
from app.agents.workers.food_agent import food_search_agent_node
from app.agents.workers.hotel_agent import hotel_react_agent_node
from app.agents.workers.poi_enrichment_agent import poi_detail_agent_node
from app.agents.workers.transport_agent import transport_agent_node
from app.core.llm import invoke_llm_with_fallback
from app.graph.nodes import budget_node, risk_notice_node, scoring_node, weather_tool_step


class OrchestratorToolkit:
    def __init__(self, state: Dict[str, Any]):
        self.state = state

    def run(self, action: str, args: Dict[str, Any] | None = None) -> Dict[str, Any]:
        args = args or {}
        if action == "plan_search_strategy":
            return self.plan_search_strategy()
        if action == "get_weather":
            return self.get_weather()
        if action == "search_attractions":
            return self.search_attractions(args)
        if action == "search_foods":
            return self.search_foods(args)
        if action == "search_hotels":
            return self.search_hotels(args)
        if action == "score_candidates":
            return self.score_candidates()
        if action == "evaluate_transport":
            return self.evaluate_transport()
        if action == "enrich_poi":
            return self.enrich_poi()
        if action == "review_itinerary":
            return self.review_itinerary()
        if action == "estimate_budget":
            return self.estimate_budget()
        if action == "build_risk_notices":
            return self.build_risk_notices()
        raise ValueError(f"Unsupported orchestrator action: {action}")

    def plan_search_strategy(self) -> Dict[str, Any]:
        query_plan = build_baseline_query_plan(self.state)
        used_fallback = True
        error = ""
        try:
            response = invoke_llm_with_fallback(
                build_planner_prompt(self.state),
                temperature=0.2,
                max_tokens=1200,
            )
            parsed = extract_json_block(_message_text(response))
            if isinstance(parsed, dict):
                planner_output = PlannerOutput.model_validate(parsed).model_dump()
                query_plan.update(
                    {
                        "travel_style": planner_output.get("travel_style") or query_plan.get("travel_style", ""),
                        "planning_focus": planner_output.get("planning_focus") or query_plan.get("planning_focus", ""),
                        "attraction_queries": dedupe(planner_output.get("attraction_queries") or query_plan.get("attraction_queries", [])),
                        "food_queries": dedupe(planner_output.get("food_queries") or query_plan.get("food_queries", [])),
                        "hotel_queries": dedupe(planner_output.get("hotel_queries") or query_plan.get("hotel_queries", [])),
                        "must_have": dedupe(planner_output.get("must_have") or query_plan.get("must_have", [])),
                    }
                )
                used_fallback = False
        except Exception as exc:
            error = str(exc)

        self.state["query_plan"] = query_plan
        return self._observation(
            "planner_agent",
            "LLM Planner 已生成搜索策略" if not used_fallback else "LLM Planner 不可用，已使用 baseline 搜索策略",
            {
                "query_plan": query_plan,
                "used_fallback": used_fallback,
                "error": error,
            },
        )

    def get_weather(self) -> Dict[str, Any]:
        update = weather_tool_step(self.state)
        self.state.update(update)
        forecast = (self.state.get("weather_data") or {}).get("forecast", []) or []
        return self._observation(
            "weather_tool",
            f"已获取 {len(forecast)} 天天气和天气影响",
            {
                "forecast_days": len(forecast),
                "weather_impacts": self.state.get("weather_impacts", []) or [],
            },
        )

    def search_attractions(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._merge_query_plan("attraction_queries", args.get("queries"))
        update = attraction_search_agent_node(self.state)
        self.state.update(update)
        candidates = self.state.get("attraction_candidates", []) or []
        return self._observation(
            "attraction_agent",
            f"已调用景点子智能体，获得 {len(candidates)} 个真实景点候选",
            {"count": len(candidates), "top_items": _top_names(candidates)},
        )

    def search_foods(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._merge_query_plan("food_queries", args.get("queries"))
        update = food_search_agent_node(self.state)
        self.state.update(update)
        candidates = self.state.get("food_candidates", []) or []
        return self._observation(
            "food_agent",
            f"已调用餐饮子智能体，获得 {len(candidates)} 个真实餐饮候选",
            {"count": len(candidates), "top_items": _top_names(candidates)},
        )

    def search_hotels(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self._merge_query_plan("hotel_queries", args.get("queries"))
        update = hotel_react_agent_node(self.state)
        self.state.update(update)
        hotels = self.state.get("hotel_options", []) or []
        return self._observation(
            "hotel_agent",
            f"已调用酒店子智能体，获得 {len(hotels)} 个真实酒店候选",
            {"count": len(hotels), "top_items": _top_names(hotels)},
        )

    def score_candidates(self) -> Dict[str, Any]:
        update = scoring_node(self.state)
        self.state.update(update)
        return self._observation(
            "scoring",
            "已完成候选评分排序",
            {
                "attractions": _top_names(self.state.get("scored_attractions", []) or []),
                "foods": _top_names(self.state.get("scored_foods", []) or []),
                "hotels": _top_names(self.state.get("scored_hotels", []) or []),
            },
        )

    def evaluate_transport(self) -> Dict[str, Any]:
        update = transport_agent_node(self.state)
        self.state.update(update)
        transport_plan = self.state.get("transport_plan", {}) or {}
        intercity_transport = self.state.get("intercity_transport") or transport_plan.get("intercity_transport") or {}
        return self._observation(
            "transport_agent",
            "已完成动线评估",
            {
                "legs": len(transport_plan.get("legs", []) or []),
                "distance_km": transport_plan.get("total_distance_km", 0),
                "duration_minutes": transport_plan.get("total_duration_minutes", 0),
                "intercity_transport": intercity_transport,
                "summary": transport_plan.get("summary", ""),
            },
        )

    def enrich_poi(self) -> Dict[str, Any]:
        update = poi_detail_agent_node(self.state)
        self.state.update(update)
        poi_data = self.state.get("poi_data", {}) or {}
        return self._observation(
            "poi_agent",
            f"已补全 {len(poi_data)} 个 POI 细节",
            {"poi_count": len(poi_data), "top_items": list(poi_data.keys())[:8]},
        )

    def review_itinerary(self) -> Dict[str, Any]:
        update = reviewer_agent_node(self.state)
        self.state.update(update)
        issues = self.state.get("review_issues", []) or []
        return self._observation(
            "reviewer_agent",
            f"Reviewer 已完成审查，剩余 {len(issues)} 个问题",
            {
                "issue_count": len(issues),
                "issues": issues[:6],
                "quality_score": self.state.get("quality_score", {}),
            },
        )

    def estimate_budget(self) -> Dict[str, Any]:
        update = budget_node(self.state)
        self.state.update(update)
        budget = self.state.get("estimated_budget", {}) or {}
        return self._observation(
            "budget",
            "已完成预算估算",
            {
                "total": budget.get("total", 0),
                "per_person": budget.get("per_person", 0),
                "currency": budget.get("currency", "CNY"),
                "is_over_budget": budget.get("is_over_budget", False),
                "intercity_transport_cost": (budget.get("intercity_transport") or {}).get("total_cost", 0),
            },
        )

    def build_risk_notices(self) -> Dict[str, Any]:
        try:
            update = risk_notice_node(self.state)
        except Exception as exc:
            self.state["risk_notices"] = [
                {
                    "type": "system",
                    "level": "low",
                    "title": "提醒生成未完成",
                    "content": f"本次行程已生成，但风险提醒生成失败：{exc}",
                    "related_day": None,
                    "related_place": "",
                }
            ]
            return self._observation(
                "risk_notice",
                "风险提醒生成失败，已降级为系统提醒",
                {"error": str(exc), "risk_notices": self.state["risk_notices"]},
            )
        self.state.update(update)
        notices = self.state.get("risk_notices", []) or []
        return self._observation(
            "risk_notice",
            f"已生成 {len(notices)} 条风险和避坑提醒",
            {"risk_notice_count": len(notices), "risk_notices": notices[:6]},
        )

    def _merge_query_plan(self, key: str, queries: Any) -> None:
        if not queries:
            return
        query_plan = dict(self.state.get("query_plan", {}) or {})
        if isinstance(queries, str):
            next_queries = [queries]
        else:
            next_queries = [str(item) for item in queries or [] if str(item).strip()]
        query_plan[key] = dedupe(next_queries)
        self.state["query_plan"] = query_plan

    def _observation(self, step: str, message: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"step": step, "message": message, "data": data}


def _message_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content or "")


def _top_names(items: List[Dict[str, Any]], limit: int = 6) -> List[str]:
    names: List[str] = []
    for item in items[:limit]:
        name = str(item.get("name", "")).strip()
        if name:
            names.append(name)
    return names
