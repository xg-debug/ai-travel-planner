import logging
from typing import Any, Dict, List

from app.agents.shared import (
    build_image_queries,
    build_poi_queries,
    candidate_has_real_source,
    enrich_activity_with_poi,
    pick_best_poi,
    select_state_candidate_for_activity,
)
from app.agents.workers.task_execution_agent import BaseTaskExecutionAgent
from app.core.config import settings
from app.orchestration.task_models import build_task_result
from app.orchestration.task_router import complete_task, get_ready_task_for_step
from app.tools.amap_tools import search_pois_tool
from app.tools.media_tools import search_photo_tool

logger = logging.getLogger(__name__)


class PoiExecutionAgent(BaseTaskExecutionAgent):
    name = "poi_agent"
    max_steps = settings.MAX_TRIP_DAYS * settings.MAX_ACTIVITIES_PER_DAY * 4 + 4

    def build_initial_context(self, state: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        plan = state.get("plan", []) or []
        queue: List[Dict[str, Any]] = []
        for day_index, day in enumerate(plan):
            for activity_index, activity in enumerate(day.get("activities", []) or []):
                queue.append(
                    {
                        "day_index": day_index,
                        "activity_index": activity_index,
                        "activity": dict(activity),
                    }
                )
        return {
            "queue": queue,
            "pending_activity": None,
            "completed": [],
            "poi_data": {},
            "used_poi_names": set(),
            "used_image_urls": set(),
            "total_activities": len(queue),
        }

    def available_actions(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
        actions: List[str] = []
        if context.get("pending_activity") is None and context.get("queue"):
            actions.append("select_activity")
        if context.get("pending_activity") is not None:
            actions.append("search_poi")
            actions.append("search_photo")
            actions.append("finish_activity")
        actions.append("finish")
        return actions

    def fallback_action(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], available: List[str], step_index: int) -> Dict[str, Any]:
        if "select_activity" in available:
            return {"thought": "先选择下一条待补全活动。", "action": "select_activity", "target": ""}
        pending = context.get("pending_activity")
        if pending and not pending.get("poi_selected") and "search_poi" in available:
            return {"thought": "先补全 POI 基础信息。", "action": "search_poi", "target": ""}
        if pending and pending.get("poi_selected") and not pending.get("photo_checked") and "search_photo" in available:
            return {"thought": "检查并补充图片。", "action": "search_photo", "target": ""}
        if "finish_activity" in available:
            return {"thought": "当前活动信息已经足够，进入下一条。", "action": "finish_activity", "target": ""}
        return super().fallback_action(state, task, context, available, step_index)

    def perform_action(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], action: Dict[str, Any], trace_entry: Dict[str, Any]) -> Dict[str, Any]:
        next_context = dict(context)
        city = state["city"]
        action_name = action.get("action")

        if action_name == "select_activity":
            queue = list(next_context.get("queue", []))
            if not queue:
                trace_entry["observation"] = "没有剩余活动需要补全。"
                return next_context
            selected = dict(queue.pop(0))
            selected["candidates"] = []
            selected["poi_selected"] = None
            selected["photo_checked"] = False
            next_context["queue"] = queue
            next_context["pending_activity"] = selected
            trace_entry["target"] = str(selected["activity"].get("location", "") or selected["activity"].get("title", ""))
            trace_entry["observation"] = "已选中 1 条活动，开始补全 POI。"
            return next_context

        pending = dict(next_context.get("pending_activity") or {})
        if not pending:
            trace_entry["observation"] = "当前没有待处理活动。"
            return next_context

        activity = dict(pending.get("activity", {}))
        location = str(activity.get("location", "")).strip()

        if action_name == "search_poi":
            used_poi_names = set(next_context.get("used_poi_names", set()))
            selected_poi = select_state_candidate_for_activity(state, activity, used_poi_names)
            candidates: List[Dict[str, Any]] = []
            if not selected_poi:
                try:
                    for query in build_poi_queries(activity, city)[:4]:
                        pois = search_pois_tool(query, city, 8)
                        if pois:
                            candidates.extend(pois)
                except Exception as exc:
                    logger.error("Error fetching POI for %s: %s", location or city, exc)
                    trace_entry["observation"] = f"poi_search_error: {exc}"
                    pending["candidates"] = []
                    next_context["pending_activity"] = pending
                    return next_context
                selected_poi = pick_best_poi(candidates, activity, city, used_poi_names)
            pending["candidates"] = candidates
            pending["poi_selected"] = selected_poi if selected_poi and candidate_has_real_source(selected_poi) else None
            if selected_poi:
                enriched = enrich_activity_with_poi(activity, selected_poi, city)
                pending["activity"] = enriched
                trace_entry["target"] = str(selected_poi.get("name", "")).strip()
                trace_entry["observation"] = f"已补全 POI：{trace_entry['target']}"
            else:
                trace_entry["observation"] = "未匹配到合适 POI，保留原活动信息。"
            next_context["pending_activity"] = pending
            return next_context

        if action_name == "search_photo":
            pending["photo_checked"] = True
            current_activity = dict(pending.get("activity", {}))
            current_image = str(current_activity.get("image", "")).strip()
            if current_image:
                trace_entry["observation"] = "已有图片，无需额外补充。"
                next_context["pending_activity"] = pending
                return next_context

            selected_poi = pending.get("poi_selected")
            if not selected_poi:
                trace_entry["observation"] = "未选中 POI，跳过图片补充。"
                next_context["pending_activity"] = pending
                return next_context

            photo = search_photo_tool(build_image_queries(city, current_activity, selected_poi), per_query=6)
            image_url = str(photo.get("url", "")).strip()
            used_image_urls = set(next_context.get("used_image_urls", set()))
            if image_url and image_url not in used_image_urls:
                current_activity["image"] = image_url
                current_activity["image_source"] = photo.get("source", "unsplash")
                current_activity["image_photographer"] = photo.get("photographer", "")
                current_activity["image_description"] = photo.get("description", "")
                used_image_urls.add(image_url)
                next_context["used_image_urls"] = used_image_urls
                trace_entry["observation"] = "已补充图片资源。"
            else:
                trace_entry["observation"] = "未找到可用新图片。"
            pending["activity"] = current_activity
            next_context["pending_activity"] = pending
            return next_context

        if action_name == "finish_activity":
            current_activity = dict(pending.get("activity", {}))
            selected_poi = pending.get("poi_selected")
            used_poi_names = set(next_context.get("used_poi_names", set()))
            poi_data = dict(next_context.get("poi_data", {}))
            location_alias = location

            if selected_poi:
                poi_name = str(selected_poi.get("name", "")).strip()
                if poi_name:
                    used_poi_names.add(poi_name)
                    enriched_poi = {**selected_poi}
                    if current_activity.get("image"):
                        enriched_poi["image_url"] = current_activity.get("image")
                    if current_activity.get("description"):
                        enriched_poi["description"] = current_activity.get("description")
                    poi_data[poi_name] = enriched_poi
                    if location_alias and location_alias != poi_name:
                        poi_data[location_alias] = enriched_poi

            completed = list(next_context.get("completed", []))
            completed.append(
                {
                    "day_index": pending["day_index"],
                    "activity_index": pending["activity_index"],
                    "activity": current_activity,
                }
            )
            next_context["completed"] = completed
            next_context["poi_data"] = poi_data
            next_context["used_poi_names"] = used_poi_names
            next_context["pending_activity"] = None
            trace_entry["observation"] = f"已完成活动补全，累计完成 {len(completed)} 条。"
            return next_context

        return next_context

    def should_finish(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], trace: List[Dict[str, Any]]) -> bool:
        return not context.get("queue") and context.get("pending_activity") is None

    def finalize(self, state: Dict[str, Any], task: Dict[str, Any], context: Dict[str, Any], trace: List[Dict[str, Any]]) -> Dict[str, Any]:
        plan = state.get("plan", []) or []
        enriched_plan: List[Dict[str, Any]] = []
        completed_map = {
            (item["day_index"], item["activity_index"]): item["activity"]
            for item in context.get("completed", [])
        }

        for day_index, day in enumerate(plan):
            next_day = {**day, "activities": []}
            for activity_index, activity in enumerate(day.get("activities", []) or []):
                next_day["activities"].append(completed_map.get((day_index, activity_index), activity))
            enriched_plan.append(next_day)

        poi_data = dict(context.get("poi_data", {}))
        completed_count = len(context.get("completed", []))
        return {
            "plan": enriched_plan,
            "poi_data": poi_data,
            "task_result": build_task_result(
                output={"poi_count": len(poi_data), "completed_activities": completed_count},
                metrics={
                    "poi_count": len(poi_data),
                    "day_count": len(enriched_plan),
                    "completed_activities": completed_count,
                    "total_activities": int(context.get("total_activities", 0) or 0),
                },
                trace=trace,
                summary=f"已按任务执行流程补全 {completed_count} 条活动的 POI 信息。",
            ),
        }


poi_execution_agent = PoiExecutionAgent()


def poi_detail_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    logger.info("Fetching POI data for %s", state["city"])
    task = get_ready_task_for_step(state, "poi_agent")
    execution_result = poi_execution_agent.run(state, task=task)
    return {
        "plan": execution_result["plan"],
        "poi_data": execution_result["poi_data"],
        **complete_task(state, "poi_agent", execution_result["task_result"]),
    }
