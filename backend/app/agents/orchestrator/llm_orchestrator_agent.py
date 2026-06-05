from __future__ import annotations

import logging
import re
from typing import Any, Dict, Generator, List

from app.agents.orchestrator.orchestrator_prompt import build_final_plan_prompt, build_orchestrator_prompt
from app.agents.orchestrator.schemas import FinalPlanModel, ORCHESTRATOR_ACTIONS, OrchestratorAction
from app.agents.orchestrator.tools import OrchestratorToolkit
from app.agents.shared import extract_json_block, normalize_itinerary
from app.core.config import settings
from app.core.llm import invoke_llm_with_fallback
from app.graph.nodes import summary_node
from app.services.itinerary_grounding_service import ground_itinerary_with_real_pois

logger = logging.getLogger(__name__)


class LLMOrchestratorRunner:
    max_steps = 12
    decision_timeout_seconds = max(settings.LLM_REQUEST_TIMEOUT_SECONDS, 90)
    final_timeout_seconds = max(settings.LLM_REQUEST_TIMEOUT_SECONDS, 180)

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        final_state: Dict[str, Any] = {}
        for event in self.stream(initial_state):
            if event["event"] == "result":
                final_state = dict(event["data"].get("state", {}) or {})
        if not final_state:
            raise RuntimeError("LLM 主控智能体未生成最终行程")
        return final_state

    def stream(self, initial_state: Dict[str, Any]) -> Generator[Dict[str, Any], None, None]:
        state = dict(initial_state)
        state.setdefault("task_results", {})
        state.setdefault("completed_tasks", [])
        state.setdefault("reflection_history", [])
        state.setdefault("recommendations", [])
        memory: Dict[str, Any] = {"orchestration_mode": "llm_agent"}
        observations: List[Dict[str, Any]] = []
        toolkit = OrchestratorToolkit(state)
        last_error = ""

        logger.info("LLM orchestrator started city=%s days=%s", state.get("city"), state.get("days"))
        yield self._status("planner_agent", "LLM 主控智能体开始理解需求并决定工具调用")

        for step_index in range(self.max_steps):
            try:
                action = self._decide_next_action(state, memory, observations, step_index, last_error)
            except Exception as exc:
                last_error = str(exc)
                logger.warning("LLM orchestrator decision failed, using controlled fallback action: %s", exc)
                action = self._fallback_next_action(state, step_index, last_error)
                yield self._status(
                    self._action_to_step(action.action),
                    f"LLM 决策暂时不可用，使用受控工具选择继续推进：{action.thought}",
                    {"error": last_error},
                )
            memory["last_thought"] = action.thought
            memory["last_action"] = action.action
            last_error = ""
            logger.info("LLM orchestrator action step=%s action=%s thought=%s", step_index + 1, action.action, action.thought)

            if action.action == "finalize":
                yield self._status("synthesizer_agent", "LLM 主控智能体开始整合最终行程")
                break

            step = self._action_to_step(action.action)
            yield self._status(step, action.thought or self._default_action_message(action.action))
            try:
                observation = toolkit.run(action.action, action.args)
            except Exception as exc:
                last_error = str(exc)
                logger.warning("LLM orchestrator tool failed action=%s error=%s", action.action, exc)
                observations.append(
                    {
                        "step": step,
                        "message": f"工具调用失败：{exc}",
                        "data": {"error": str(exc), "action": action.action},
                    }
                )
                continue

            observations.append(observation)
            self._merge_observation_memory(memory, observation)
            logger.info("LLM orchestrator observation step=%s message=%s", observation.get("step"), observation.get("message"))
            yield self._status(observation["step"], observation["message"], observation.get("data", {}))

            if self._ready_to_finalize(state) and step_index >= 5:
                yield self._status("synthesizer_agent", "真实候选、天气、评分和动线信息已足够，开始最终整合")
                break

        self._ensure_grounding_tools(state, observations, memory, toolkit)

        logger.info("LLM orchestrator final synthesis started")
        try:
            final_plan = self._build_final_plan(state, memory, observations)
        except Exception as exc:
            logger.exception("LLM final synthesis failed, using grounded fallback itinerary: %s", exc)
            final_plan = self._build_grounded_fallback_plan(state, exc)
            observations.append(
                {
                    "step": "synthesizer_agent",
                    "message": "LLM 最终整合失败，已使用真实候选数据生成降级行程",
                    "data": {"error": str(exc), "used_fallback": True},
                }
            )
        state["plan"] = final_plan["itinerary"]
        state["draft_plan"] = final_plan["itinerary"]
        state["reviewed_plan"] = final_plan["itinerary"]
        state["final_output"] = final_plan["final_output"]
        yield self._status("route_grounding", "将 LLM 行程落地到真实 POI 并修正每日动线")
        grounding_update = ground_itinerary_with_real_pois(state)
        state.update(grounding_update)
        if grounding_update.get("route_patch_actions"):
            state.update(summary_node(state))
            observations.append(
                {
                    "step": "route_grounding",
                    "message": "已将 LLM 行程落地到真实 POI 并修正每日动线",
                    "data": {
                        "patch_count": len(grounding_update.get("route_patch_actions", []) or []),
                        "route_quality": grounding_update.get("route_quality", {}),
                    },
                }
            )
        yield self._status("synthesizer_agent_done", "LLM 已完成详细行程整合", {"days": len(state.get("plan", []) or [])})

        if not state.get("poi_data"):
            yield self._status("poi_agent", "补全最终行程中的 POI 细节")
            observation = toolkit.enrich_poi()
            observations.append(observation)
            yield self._status(observation["step"], observation["message"], observation.get("data", {}))

        yield self._status("reviewer_agent", "调用 reviewer 子智能体审查 LLM 行程")
        review_observation = toolkit.review_itinerary()
        observations.append(review_observation)
        yield self._status(review_observation["step"], review_observation["message"], review_observation.get("data", {}))

        if state.get("review_issues"):
            yield self._status(
                "reflection_rerun",
                "Reviewer 已自动修补可处理问题，剩余问题将写入风险提醒",
                {"issues": len(state.get("review_issues", []) or [])},
            )
            yield self._status("poi_agent", "修正后重新补全 POI 细节")
            poi_observation = toolkit.enrich_poi()
            observations.append(poi_observation)
            yield self._status(poi_observation["step"], poi_observation["message"], poi_observation.get("data", {}))

        yield self._status("budget", "估算最终行程预算")
        budget_observation = toolkit.estimate_budget()
        observations.append(budget_observation)
        yield self._status(budget_observation["step"], budget_observation["message"], budget_observation.get("data", {}))

        yield self._status("risk_notice", "生成风险和避坑提醒")
        risk_observation = toolkit.build_risk_notices()
        observations.append(risk_observation)
        yield self._status(risk_observation["step"], risk_observation["message"], risk_observation.get("data", {}))

        yield self._status("summary", "整理最终输出")
        if not state.get("final_output"):
            state.update(summary_node(state))

        yield {"event": "result", "data": {"state": state, "observations": observations}}
        logger.info("LLM orchestrator completed city=%s days=%s", state.get("city"), len(state.get("plan", []) or []))

    def _decide_next_action(
        self,
        state: Dict[str, Any],
        memory: Dict[str, Any],
        observations: List[Dict[str, Any]],
        step_index: int,
        last_error: str,
    ) -> OrchestratorAction:
        prompt = build_orchestrator_prompt(
            state,
            memory,
            observations,
            step_index=step_index,
            last_error=last_error,
        )
        response = invoke_llm_with_fallback(
            prompt,
            temperature=0.2,
            max_tokens=600,
            request_timeout=self.decision_timeout_seconds,
        )
        parsed = extract_json_block(_message_text(response))
        if not isinstance(parsed, dict):
            raise RuntimeError("LLM 主控智能体未返回合法 JSON 决策")
        action = OrchestratorAction.model_validate(parsed)
        if action.action not in ORCHESTRATOR_ACTIONS:
            raise RuntimeError(f"LLM 主控智能体返回了不支持的动作：{action.action}")
        if action.action == "finalize" and not self._has_required_context(state):
            return self._next_required_action(state, action.thought)
        return action

    def _build_final_plan(
        self,
        state: Dict[str, Any],
        memory: Dict[str, Any],
        observations: List[Dict[str, Any]],
        *,
        repair_error: str = "",
        previous_output: Any = None,
    ) -> Dict[str, Any]:
        prompt = build_final_plan_prompt(
            state,
            memory,
            observations,
            repair_error=repair_error,
            previous_output=previous_output,
        )
        max_tokens = min(3200, max(1800, int(state.get("days", 1) or 1) * 700))
        response = invoke_llm_with_fallback(
            prompt,
            temperature=0.35,
            max_tokens=max_tokens,
            request_timeout=self.final_timeout_seconds,
        )
        parsed = extract_json_block(_message_text(response))
        try:
            final_model = FinalPlanModel.model_validate(parsed)
        except Exception as exc:
            repair_prompt = build_final_plan_prompt(
                state,
                memory,
                observations,
                repair_error=f"上一次输出无法通过结构化校验：{exc}。请只返回合法 JSON。",
                previous_output=parsed,
            )
            repair_response = invoke_llm_with_fallback(
                repair_prompt,
                temperature=0.2,
                max_tokens=max_tokens,
                request_timeout=self.final_timeout_seconds,
            )
            repaired = extract_json_block(_message_text(repair_response))
            final_model = FinalPlanModel.model_validate(repaired)

        itinerary = normalize_itinerary(final_model.itinerary, state)
        if not any(day.get("activities") for day in itinerary):
            raise RuntimeError("LLM 最终输出没有可用活动")
        return {
            "itinerary": itinerary,
            "final_output": final_model.final_output,
        }

    def _build_grounded_fallback_plan(self, state: Dict[str, Any], error: Exception) -> Dict[str, Any]:
        days = max(int(state.get("days", 1) or 1), 1)
        city = state.get("city", "")
        attractions = list(state.get("scored_attractions") or state.get("attraction_candidates") or [])
        foods = list(state.get("scored_foods") or state.get("food_candidates") or [])
        hotels = list(state.get("scored_hotels") or state.get("hotel_options") or [])
        weather_impacts = list(state.get("weather_impacts", []) or [])

        if not attractions or not foods or not hotels:
            raise RuntimeError(f"LLM 最终整合失败，且真实候选不足，无法降级生成行程：{error}") from error

        itinerary: List[Dict[str, Any]] = []
        for index in range(days):
            hotel = hotels[index % len(hotels)]
            morning = attractions[(index * 2) % len(attractions)]
            afternoon = attractions[(index * 2 + 1) % len(attractions)] if len(attractions) > 1 else morning
            lunch = foods[index % len(foods)]
            dinner = foods[(index + 1) % len(foods)] if len(foods) > 1 else lunch
            impact = weather_impacts[index] if index < len(weather_impacts) else {}
            itinerary.append(
                {
                    "day": index + 1,
                    "date": None,
                    "theme": f"{city}真实地点精简行程",
                    "summary": f"{_name(morning)} - {_name(lunch)} - {_name(afternoon)} - {_name(dinner)}",
                    "weather_advice": impact.get("advice", "根据实时天气灵活调整户外活动顺序。"),
                    "hotel_recommendation": {
                        "name": _name(hotel),
                        "price_estimate": hotel.get("price", ""),
                        "address": hotel.get("address", ""),
                        "reason": hotel.get("reason", "基于真实酒店候选选择，便于衔接每日路线。"),
                        "source": hotel.get("source", ""),
                        "source_id": hotel.get("id", ""),
                        "coordinates": _coordinates(hotel),
                    },
                    "activities": [
                        _fallback_activity(morning, "09:30-11:30", "景点游览"),
                        _fallback_activity(lunch, "12:00-13:30", "美食餐饮"),
                        _fallback_activity(afternoon, "14:30-17:00", "景点游览"),
                        _fallback_activity(dinner, _fallback_dinner_time(index), "美食餐饮"),
                    ],
                }
            )

        return {
            "itinerary": normalize_itinerary(itinerary, state),
            "final_output": f"# {city} {days}天行程规划\n\nLLM 最终整合超时或失败，系统已基于真实景点、餐饮、酒店候选生成可用降级行程。建议重新生成以获得更完整的文字规划。",
        }

    def _ensure_grounding_tools(
        self,
        state: Dict[str, Any],
        observations: List[Dict[str, Any]],
        memory: Dict[str, Any],
        toolkit: OrchestratorToolkit,
    ) -> None:
        required_actions: List[str] = []
        if not state.get("query_plan"):
            required_actions.append("plan_search_strategy")
        if not state.get("weather_data"):
            required_actions.append("get_weather")
        if not state.get("attraction_candidates"):
            required_actions.append("search_attractions")
        if not state.get("food_candidates"):
            required_actions.append("search_foods")
        if not state.get("hotel_options"):
            required_actions.append("search_hotels")
        if not (state.get("scored_attractions") and state.get("scored_foods") and state.get("scored_hotels")):
            required_actions.append("score_candidates")
        if not state.get("transport_plan"):
            required_actions.append("evaluate_transport")

        for action in required_actions:
            observation = toolkit.run(action, {})
            observations.append(observation)
            self._merge_observation_memory(memory, observation)

    def _has_required_context(self, state: Dict[str, Any]) -> bool:
        return bool(
            state.get("query_plan")
            and state.get("weather_data")
            and state.get("attraction_candidates")
            and state.get("food_candidates")
            and state.get("hotel_options")
        )

    def _ready_to_finalize(self, state: Dict[str, Any]) -> bool:
        return bool(
            self._has_required_context(state)
            and state.get("scored_attractions")
            and state.get("scored_foods")
            and state.get("scored_hotels")
            and state.get("transport_plan")
        )

    def _fallback_next_action(self, state: Dict[str, Any], step_index: int, reason: str) -> OrchestratorAction:
        if not state.get("query_plan"):
            return OrchestratorAction(thought="先生成搜索策略，避免缺少查询方向。", action="plan_search_strategy")
        if not state.get("weather_data"):
            return OrchestratorAction(thought="先获取天气，为后续排期提供约束。", action="get_weather")
        if not state.get("attraction_candidates"):
            return OrchestratorAction(thought="补齐真实景点候选。", action="search_attractions")
        if not state.get("food_candidates"):
            return OrchestratorAction(thought="补齐真实餐饮候选。", action="search_foods")
        if not state.get("hotel_options"):
            return OrchestratorAction(thought="补齐真实酒店候选。", action="search_hotels")
        if not (state.get("scored_attractions") and state.get("scored_foods") and state.get("scored_hotels")):
            return OrchestratorAction(thought="对候选进行评分排序，提供取舍依据。", action="score_candidates")
        if not state.get("transport_plan"):
            return OrchestratorAction(thought="评估路线动线，避免最终行程过度绕路。", action="evaluate_transport")
        return OrchestratorAction(thought=f"工具信息已足够，进入最终整合。上一轮 LLM 错误：{reason}", action="finalize")

    def _next_required_action(self, state: Dict[str, Any], thought: str) -> OrchestratorAction:
        if not state.get("query_plan"):
            return OrchestratorAction(thought=thought or "缺少搜索策略，先理解需求。", action="plan_search_strategy")
        if not state.get("weather_data"):
            return OrchestratorAction(thought=thought or "缺少天气事实，先查询天气。", action="get_weather")
        if not state.get("attraction_candidates"):
            return OrchestratorAction(thought=thought or "缺少真实景点候选，先搜索景点。", action="search_attractions")
        if not state.get("food_candidates"):
            return OrchestratorAction(thought=thought or "缺少真实餐饮候选，先搜索餐饮。", action="search_foods")
        if not state.get("hotel_options"):
            return OrchestratorAction(thought=thought or "缺少真实酒店候选，先搜索酒店。", action="search_hotels")
        return OrchestratorAction(thought=thought or "信息已足够，进入最终整合。", action="finalize")

    def _merge_observation_memory(self, memory: Dict[str, Any], observation: Dict[str, Any]) -> None:
        memory.setdefault("completed_steps", [])
        step = observation.get("step")
        if step and step not in memory["completed_steps"]:
            memory["completed_steps"].append(step)

    def _status(self, step: str, message: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
        payload = {"step": step, "message": message}
        if data:
            payload.update(data)
        return {"event": "status", "data": payload}

    def _action_to_step(self, action: str) -> str:
        return {
            "plan_search_strategy": "planner_agent",
            "get_weather": "weather_tool",
            "search_attractions": "attraction_agent",
            "search_foods": "food_agent",
            "search_hotels": "hotel_agent",
            "score_candidates": "planner_agent",
            "evaluate_transport": "transport_agent",
            "enrich_poi": "poi_agent",
            "review_itinerary": "reviewer_agent",
            "estimate_budget": "budget",
            "build_risk_notices": "risk_notice",
        }.get(action, "planner_agent")

    def _default_action_message(self, action: str) -> str:
        return {
            "plan_search_strategy": "理解需求并生成搜索策略",
            "get_weather": "获取天气信息",
            "search_attractions": "搜索真实景点候选",
            "search_foods": "搜索真实餐饮候选",
            "search_hotels": "搜索真实酒店候选",
            "score_candidates": "为候选排序",
            "evaluate_transport": "评估动线",
            "enrich_poi": "补全 POI 信息",
            "review_itinerary": "审查行程质量",
            "estimate_budget": "估算预算",
            "build_risk_notices": "生成风险提醒",
        }.get(action, "执行工具调用")


def _name(item: Dict[str, Any]) -> str:
    return str((item or {}).get("name", "")).strip() or "待定地点"


def _coordinates(item: Dict[str, Any]) -> Dict[str, float] | None:
    lat = _safe_float_or_none(item.get("lat"))
    lng = _safe_float_or_none(item.get("lng"))
    if lat is None or lng is None:
        return None
    return {"lat": lat, "lng": lng}


def _fallback_activity(item: Dict[str, Any], time_text: str, activity_type: str) -> Dict[str, Any]:
    item = item or {}
    name = _name(item)
    description_parts = [
        str(item.get("description", "")).strip(),
        str(item.get("address", "")).strip(),
        str(item.get("opening_hours", "")).strip(),
    ]
    description = "；".join(part for part in description_parts if part) or f"{name}来自真实候选数据，适合纳入本次路线。"
    price = _safe_int_or_zero(item.get("price"))
    is_food = "餐" in activity_type or "美食" in activity_type
    activity = {
        "time": time_text,
        "title": name,
        "description": description,
        "type": activity_type,
        "location": name,
        "duration": 90,
        "cost_estimate": price if is_food else 0,
        "ticket_price": 0 if is_food else price if price < 300 else 0,
        "tips": str(item.get("tips", "")).strip() or "建议根据现场客流和开放时间微调。",
        "transportation": "步行/公共交通/网约车",
        "reason": item.get("reason", ""),
        "score": item.get("score"),
        "opening_hours": item.get("opening_hours", ""),
    }
    if item.get("image_url"):
        activity["image"] = item.get("image_url")
    lat = _safe_float_or_none(item.get("lat"))
    lng = _safe_float_or_none(item.get("lng"))
    if lat is not None and lng is not None:
        activity["coordinates"] = {"lat": lat, "lng": lng}
    if item.get("source"):
        activity["source"] = item.get("source")
    if item.get("id"):
        activity["source_id"] = item.get("id")
    return activity


def _fallback_dinner_time(day_index: int) -> str:
    start_minutes = 17 * 60 + 50 + (day_index % 3) * 15
    end_minutes = start_minutes + 80
    return f"{_clock(start_minutes)}-{_clock(end_minutes)}"


def _clock(total_minutes: int) -> str:
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _safe_int_or_zero(value: Any) -> int:
    try:
        if isinstance(value, (int, float)):
            return int(value)
        matched = re.search(r"\d+(?:\.\d+)?", str(value or ""))
        return int(float(matched.group())) if matched else 0
    except Exception:
        return 0


def _safe_float_or_none(value: Any) -> float | None:
    try:
        if value in (None, "", 0, 0.0):
            return None
        return float(value)
    except Exception:
        return None


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


llm_orchestrator_runner = LLMOrchestratorRunner()
