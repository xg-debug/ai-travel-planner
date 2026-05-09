from typing import Any, Dict, List

from app.agents.schemas import ReflectionContextModel, ReflectionHistoryEntryModel, ReviewIssueModel
from app.agents.shared import normalize_itinerary
from app.orchestration.task_models import build_task_result
from app.orchestration.task_router import complete_task, reset_task_chain, task_can_retry


def _issue(issue_type: str, severity: str, day: int | None, message: str) -> Dict[str, Any]:
    return ReviewIssueModel(
        type=issue_type,
        severity=severity,
        day=day,
        message=message,
    ).model_dump()


def _review_itinerary(plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    seen_locations: set[str] = set()
    for day in plan:
        day_no = int(day.get("day") or 0) or None
        activities = day.get("activities", []) or []
        if len(activities) < 5:
            issues.append(_issue("missing_activities", "major", day_no, "活动数量不足 5 个"))
        if not day.get("hotel_recommendation"):
            issues.append(_issue("missing_hotel", "major", day_no, "当天缺少酒店推荐"))

        food_hits = 0
        for activity in activities:
            text = " ".join(
                [
                    str(activity.get("title", "")),
                    str(activity.get("type", "")),
                    str(activity.get("description", "")),
                    str(activity.get("location", "")),
                ]
            )
            if any(token in text for token in ("早餐", "午餐", "晚餐", "餐", "美食", "小吃")):
                food_hits += 1
            location = str(activity.get("location", "")).strip()
            if location and location in seen_locations:
                issues.append(_issue("duplicate_location", "minor", day_no, f"地点重复：{location}"))
            if location:
                seen_locations.add(location)

        if food_hits == 0:
            issues.append(_issue("missing_food", "minor", day_no, "当天缺少明确餐饮活动"))
    return issues


def _classify_activity_category(activity: Dict[str, Any]) -> str:
    text = " ".join(
        [
            str(activity.get("title", "")),
            str(activity.get("type", "")),
            str(activity.get("description", "")),
            str(activity.get("location", "")),
        ]
    )
    if any(token in text for token in ("早餐", "午餐", "晚餐", "餐", "美食", "小吃", "咖啡", "茶馆", "火锅", "面")):
        return "food"
    return "attraction"


def _pick_replacement_candidate(state: Dict[str, Any], used_locations: set[str], category: str) -> Dict[str, Any] | None:
    candidate_groups = []
    if category == "food":
        candidate_groups.append(state.get("food_candidates", []) or [])
    else:
        candidate_groups.append(state.get("attraction_candidates", []) or [])

    for group in candidate_groups:
        for item in group:
            name = str(item.get("name", "")).strip()
            if name and name not in used_locations:
                used_locations.add(name)
                return dict(item)
    return None


def _patch_itinerary(plan: List[Dict[str, Any]], state: Dict[str, Any], issues: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    patched = normalize_itinerary(plan, state)
    patch_actions: List[Dict[str, Any]] = []
    used_locations = {
        str(activity.get("location", "")).strip()
        for day in patched
        for activity in (day.get("activities", []) or [])
        if str(activity.get("location", "")).strip()
    }

    for issue in issues:
        day_no = issue.get("day")
        if not isinstance(day_no, int) or day_no <= 0 or day_no > len(patched):
            continue
        day = patched[day_no - 1]
        activities = day.get("activities", []) or []

        if issue["type"] == "missing_food":
            replacement = _pick_replacement_candidate(state, used_locations, "food")
            replacement_name = str((replacement or {}).get("name", "")).strip()
            if replacement_name:
                activities.insert(
                    min(2, len(activities)),
                    {
                        "time": "12:30-13:30",
                        "title": "补充本地特色用餐",
                        "description": f"根据 review 自动补充更合理的餐饮安排，优先使用真实餐饮候选 {replacement_name}。",
                        "type": "美食餐饮",
                        "location": replacement_name,
                        "duration": 60,
                        "cost_estimate": 90,
                        "ticket_price": 0,
                        "tips": "建议错峰到店。",
                        "transportation": "步行/网约车",
                        "source": replacement.get("source", ""),
                        "source_id": replacement.get("id", ""),
                    },
                )
                patch_actions.append({"day": day_no, "action": "insert_food", "location": replacement_name})

        elif issue["type"] == "missing_activities":
            while len(activities) < 5:
                replacement = _pick_replacement_candidate(state, used_locations, "attraction")
                candidate_location = str((replacement or {}).get("name", "")).strip()
                if not candidate_location:
                    break
                next_activity = {
                    "time": "15:30-17:00",
                    "title": candidate_location,
                    "description": f"基于真实候选结果补充的行程活动：{candidate_location}。",
                    "type": "景点游览",
                    "location": candidate_location,
                    "duration": 90,
                    "cost_estimate": 0,
                    "ticket_price": 0,
                    "tips": "建议根据开放时间调整顺序。",
                    "transportation": "步行/网约车",
                    "source": replacement.get("source", ""),
                    "source_id": replacement.get("id", ""),
                }
                activities.append(next_activity)
                patch_actions.append({"day": day_no, "action": "append_activity", "location": next_activity.get("location", "")})

        elif issue["type"] == "duplicate_location":
            duplicate_name = issue["message"].split("：", 1)[-1].strip()
            replaced = False
            for activity in activities:
                if str(activity.get("location", "")).strip() != duplicate_name:
                    continue
                category = _classify_activity_category(activity)
                replacement = _pick_replacement_candidate(state, used_locations, category)
                replacement_name = str((replacement or {}).get("name", "")).strip()
                if replacement_name and replacement_name != duplicate_name:
                    activity["location"] = replacement_name
                    activity["title"] = (
                        replacement_name
                        if category != "food"
                        else str(activity.get("title", "")).replace(duplicate_name, replacement_name) or replacement_name
                    )
                    activity["description"] = f"基于真实候选结果替换重复地点，调整为 {replacement_name}。"
                    activity["source"] = replacement.get("source", "")
                    activity["source_id"] = replacement.get("id", "")
                    patch_actions.append({"day": day_no, "action": "replace_duplicate", "from": duplicate_name, "to": replacement_name})
                    replaced = True
                    break

        elif issue["type"] == "missing_hotel":
            hotel_options = state.get("hotel_options", []) or []
            if hotel_options:
                hotel = hotel_options[0]
                day["hotel_recommendation"] = {
                    "name": hotel.get("name", state["city"]),
                    "price_estimate": hotel.get("price", ""),
                    "address": hotel.get("address", state["city"]),
                    "reason": "review 阶段自动补充住宿建议，确保每日行程闭环。",
                }
                patch_actions.append({"day": day_no, "action": "fill_hotel", "location": hotel.get("name", "")})

        day["activities"] = activities[:6]

    return normalize_itinerary(patched, state), patch_actions


def _needs_rerun(issues: List[Dict[str, Any]], patch_actions: List[Dict[str, Any]], state: Dict[str, Any]) -> bool:
    if not issues:
        return False
    major_count = len([issue for issue in issues if issue.get("severity") == "major"])
    if major_count >= 2:
        return task_can_retry(state, "synthesizer_agent")
    if len(issues) >= max(4, state.get("days", 1) * 2) and len(patch_actions) < len(issues) // 2:
        return task_can_retry(state, "synthesizer_agent")
    return False


def reviewer_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    draft_plan = state.get("plan") or state.get("draft_plan") or []
    reviewed_plan = normalize_itinerary(draft_plan, state)
    review_issues = _review_itinerary(reviewed_plan)
    patched_plan, patch_actions = _patch_itinerary(reviewed_plan, state, review_issues)
    post_patch_issues = _review_itinerary(patched_plan)
    reflection_history = list(state.get("reflection_history", []) or [])

    rerun_required = _needs_rerun(post_patch_issues, patch_actions, state)
    review_summary = (
        f"发现 {len(review_issues)} 个问题，已自动修补 {len(patch_actions)} 处。"
        if review_issues
        else "未发现明显问题，行程可直接进入后处理。"
    )

    reflection_entry = {
        "summary": review_summary,
        "issue_count": len(review_issues),
        "post_patch_issue_count": len(post_patch_issues),
        "patch_actions": patch_actions,
        "rerun_required": rerun_required,
    }
    reflection_history.append(ReflectionHistoryEntryModel.model_validate(reflection_entry).model_dump())

    result = {
        "plan": patched_plan,
        "reviewed_plan": patched_plan,
        "review_issues": post_patch_issues,
        "reflection_history": reflection_history,
    }

    if rerun_required:
        completion = complete_task(
            state,
            "reviewer_agent",
            build_task_result(
                output={"patch_actions": patch_actions, "rerun_required": rerun_required},
                metrics={
                    "issue_count": len(review_issues),
                    "post_patch_issue_count": len(post_patch_issues),
                    "patch_count": len(patch_actions),
                },
                trace=patch_actions,
                quality={"status": "rerun"},
                summary=review_summary,
            ),
        )
        rerun_state = {**state, **completion}
        result.update(
            {
                "reflection_context": ReflectionContextModel(
                    action="rerun_synthesizer",
                    summary=review_summary,
                    issues=[ReviewIssueModel.model_validate(issue) for issue in post_patch_issues],
                ).model_dump()
            }
        )
        result.update(
            reset_task_chain(
                rerun_state,
                ["synthesizer_agent", "poi_agent", "reviewer_agent"],
                reason="reflection requested synthesizer rerun",
            )
        )
    else:
        result.update(
            complete_task(
                state,
                "reviewer_agent",
                build_task_result(
                    output={"patch_actions": patch_actions, "rerun_required": rerun_required},
                    metrics={
                        "issue_count": len(review_issues),
                        "post_patch_issue_count": len(post_patch_issues),
                        "patch_count": len(patch_actions),
                    },
                    trace=patch_actions,
                    quality={"status": "patched" if patch_actions else "passed"},
                    summary=review_summary,
                ),
            )
        )
    return result
