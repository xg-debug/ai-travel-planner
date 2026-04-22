import json
import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, List

from app.agents.city_knowledge import (
    contains_any,
    get_generic_location_keywords,
    has_branch_marker,
    score_food_locality,
)
from app.services.amap_service import search_hotels, search_pois
from app.services.unsplash_service import search_best_photo

logger = logging.getLogger(__name__)

BAD_POI_KEYWORDS = (
    "停车场",
    "停车",
    "售票处",
    "票务",
    "票务中心",
    "检票口",
    "游客中心",
    "服务区",
    "入口",
    "出口",
    "上客点",
    "下客点",
    "乘车点",
    "摆渡车",
    "西票务中心",
    "东票务中心",
    "南票务中心",
    "北票务中心",
)

GENERIC_FALLBACK_LOCATION_KEYWORDS = (
    "城市公园",
    "城市地标景区",
    "博物馆与历史街区",
    "夜景商圈",
    "本地早餐店",
    "热门餐厅聚集区",
    "推荐地点",
)


def dedupe(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        matched = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(matched.group()) if matched else default
    except Exception:
        return default


def extract_price_amount(value: Any) -> float:
    amount = safe_float(value, 0.0)
    return amount if amount >= 0 else 0.0


def normalize_preferences(preferences: List[str] | None) -> List[str]:
    alias_map = {
        "人文": "culture",
        "文化": "culture",
        "历史": "culture",
        "博物馆": "culture",
        "美食": "food",
        "餐饮": "food",
        "小吃": "food",
        "自然": "nature",
        "户外": "nature",
        "公园": "nature",
        "休闲": "nature",
        "购物": "shopping",
        "夜生活": "shopping",
        "夜游": "shopping",
        "拍照": "photography",
        "摄影": "photography",
        "打卡": "photography",
    }
    normalized: List[str] = []
    for item in preferences or []:
        text = str(item or "").strip().lower()
        if not text:
            continue
        normalized.append(alias_map.get(text, text))
    return dedupe(normalized)


def normalize_search_query(query: str, city: str) -> List[str]:
    text = str(query or "").strip()
    if not text:
        return []

    normalized = text.replace("（", "(").replace("）", ")")
    normalized = re.sub(r"[()]", " ", normalized)
    normalized = re.sub(r"[·,，/、;；]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    variants = [normalized]
    without_city = normalized.replace(city, " ").strip()
    if without_city:
        variants.append(without_city)

    trimmed = re.sub(
        r"(本地人推荐|推荐|高分|高评分|黑珍珠|摄影|观景台|私家园林|精品|豪华|日落|生态|工作室|别墅式)",
        " ",
        without_city or normalized,
    )
    trimmed = re.sub(r"\s+", " ", trimmed).strip()
    if trimmed:
        variants.append(trimmed)

    tokens = [token for token in trimmed.split() if token]
    if len(tokens) >= 2:
        variants.append(" ".join(tokens[:2]))
    if tokens:
        variants.append(tokens[0])

    return dedupe([item for item in variants if item and item != city])


def is_generic_location(location: str, city: str) -> bool:
    text = str(location or "").strip()
    if not text:
        return True
    generic_keywords = get_generic_location_keywords()
    if contains_any(text, generic_keywords):
        return True
    if re.search(r"\d+-\d+$", text):
        return True
    if text.startswith(city) and contains_any(text, generic_keywords):
        return True
    if contains_any(text, GENERIC_FALLBACK_LOCATION_KEYWORDS):
        return True
    return False


def is_bad_poi(name: str, type_text: str = "") -> bool:
    searchable = f"{name} {type_text}".strip()
    if not searchable:
        return True
    return contains_any(searchable, BAD_POI_KEYWORDS)


def build_poi_queries(activity: Dict[str, Any], city: str) -> List[str]:
    title = str(activity.get("title", ""))
    act_type = str(activity.get("type", ""))
    description = str(activity.get("description", ""))
    location = str(activity.get("location", ""))
    hint_text = " ".join([title, act_type, description, location])

    queries: List[str] = []
    if location and not is_generic_location(location, city):
        queries.append(location)

    if "早餐" in hint_text:
        queries.extend(["老字号早餐", "本地早餐店", "人气早餐"])
    elif "午餐" in hint_text or "晚餐" in hint_text or "餐" in hint_text or "美食" in hint_text:
        queries.extend(["本地特色餐厅", "特色餐厅", "人气餐厅"])
    elif "夜景" in hint_text or "商圈" in hint_text:
        queries.extend(["夜景", "夜游", "步行街"])
    elif "公园" in hint_text or "户外" in hint_text or "自然" in hint_text:
        queries.extend(["城市公园", "公园", "湿地公园"])
    elif "博物" in hint_text or "历史" in hint_text or "文化" in hint_text:
        queries.extend(["博物馆", "历史街区", "文化景点"])
    else:
        queries.extend(["地标景点", "经典景点", "热门景点"])

    if title and title not in queries and len(title) <= 24:
        queries.insert(0, title if city in title else f"{city}{title}")
    return dedupe([f"{city}{query}" if city not in query else query for query in queries])


def score_poi_candidate(
    poi: Dict[str, Any],
    activity: Dict[str, Any],
    city: str,
    used_poi_names: set[str],
) -> float:
    name = str(poi.get("name", ""))
    if not name or name in used_poi_names:
        return -1
    type_text = str(poi.get("type", ""))
    if is_bad_poi(name, type_text):
        return -1

    score = float(poi.get("rating", 0) or 0)
    if poi.get("image_url"):
        score += 2.5

    hint_text = " ".join(
        [
            str(activity.get("title", "")),
            str(activity.get("type", "")),
            str(activity.get("description", "")),
            str(activity.get("location", "")),
            str(poi.get("type", "")),
            name,
        ]
    )
    if "早餐" in hint_text and ("餐饮" in type_text or "小吃" in type_text or "面馆" in type_text or "咖啡" not in type_text):
        score += 3
    if ("午餐" in hint_text or "晚餐" in hint_text or "餐" in hint_text) and ("餐饮" in type_text or "中餐" in type_text or "美食" in type_text):
        score += 3
    if ("夜景" in hint_text or "商圈" in hint_text) and ("商场" in type_text or "购物" in type_text or "风景" in type_text or "步行街" in name):
        score += 2.5
    if ("公园" in hint_text or "湿地" in hint_text) and ("公园" in type_text or "风景名胜" in type_text):
        score += 2.5
    if ("博物" in hint_text or "文化" in hint_text or "历史" in hint_text) and ("博物馆" in type_text or "寺庙" in type_text or "景点" in type_text):
        score += 2.5
    if city and city in name:
        score += 0.8
    if is_generic_location(name, city):
        score -= 2.5
    return score


def pick_best_poi(
    candidates: List[Dict[str, Any]],
    activity: Dict[str, Any],
    city: str,
    used_poi_names: set[str],
) -> Dict[str, Any] | None:
    best_poi = None
    best_score = -1.0
    for poi in candidates:
        score = score_poi_candidate(poi, activity, city, used_poi_names)
        if score > best_score:
            best_score = score
            best_poi = poi
    return best_poi


def activity_category(activity: Dict[str, Any]) -> str:
    hint_text = " ".join(
        [
            str(activity.get("title", "")),
            str(activity.get("type", "")),
            str(activity.get("description", "")),
            str(activity.get("location", "")),
        ]
    )
    if any(token in hint_text for token in ("早餐", "午餐", "晚餐", "餐", "美食", "小吃")):
        return "food"
    if any(token in hint_text for token in ("酒店", "宾馆", "住宿", "民宿")):
        return "hotel"
    return "attraction"


def select_state_candidate_for_activity(
    state: Dict[str, Any],
    activity: Dict[str, Any],
    used_poi_names: set[str],
) -> Dict[str, Any] | None:
    category = activity_category(activity)
    if category == "food":
        candidate_groups = [state.get("food_candidates", []) or [], state.get("attraction_candidates", []) or []]
    elif category == "hotel":
        candidate_groups = [state.get("hotel_options", []) or []]
    else:
        candidate_groups = [state.get("attraction_candidates", []) or [], state.get("food_candidates", []) or []]

    city = state["city"]
    best_poi = None
    best_score = -1.0
    for candidates in candidate_groups:
        for poi in candidates:
            score = score_poi_candidate(poi, activity, city, used_poi_names)
            if score > best_score:
                best_score = score
                best_poi = poi
    return best_poi


def build_poi_story(city: str, activity: Dict[str, Any], poi: Dict[str, Any]) -> str:
    name = str(poi.get("name", "")).strip()
    address = str(poi.get("address", city)).strip()
    poi_type = str(poi.get("type", "")).strip()
    opening_hours = str(poi.get("opening_hours", "")).strip()
    hint_text = " ".join(
        [
            str(activity.get("title", "")),
            str(activity.get("type", "")),
            str(activity.get("description", "")),
            str(activity.get("location", "")),
        ]
    )

    if "早餐" in hint_text:
        return f"{name}适合放在早上作为行程开场，位置在{address}，更适合先尝到西安本地早餐口味，再顺路进入当天安排。"
    if "午餐" in hint_text or "晚餐" in hint_text or "餐" in hint_text:
        return f"{name}可以作为当天的正餐落点，靠近{address}，安排在景点之间更顺路，也更容易吃到有地方特色的菜式。"
    if "夜景" in hint_text or "商圈" in hint_text:
        return f"{name}更适合放在傍晚到夜间，周边氛围和可逛性会更完整，适合把夜游和晚餐安排在同一段节奏里。"
    if "公园" in hint_text or "户外" in hint_text or "自然" in hint_text:
        return f"{name}适合安排一段慢节奏步行时间，在{address}附近散步休息，既能拍照，也能给当天行程留出缓冲。"
    if "博物" in hint_text or "文化" in hint_text or "历史" in hint_text:
        suffix = f"，开放时段通常为{opening_hours}" if opening_hours else ""
        return f"{name}适合作为了解{city}人文历史的一站，内容更偏向{poi_type or '文化体验'}{suffix}，慢慢看会比匆忙打卡更有收获。"
    return f"{name}位于{address}，更适合作为当天路线中的一个真实停留点，兼顾到达便利性和现场体验。"


def build_image_queries(city: str, activity: Dict[str, Any], poi: Dict[str, Any]) -> List[str]:
    poi_name = str(poi.get("name", "")).strip()
    poi_type = str(poi.get("type", "")).strip()
    activity_type = str(activity.get("type", "")).strip()
    title = str(activity.get("title", "")).strip()
    simple_type = poi_type.split(";")[0].strip() if poi_type else ""
    is_food = any(token in f"{poi_type} {activity_type} {title}" for token in ("餐饮", "早餐", "午餐", "晚餐", "美食"))
    is_hotel = any(token in f"{poi_type} {poi_name}" for token in ("酒店", "宾馆", "民宿", "住宿"))
    is_park = any(token in f"{poi_type} {poi_name} {title}" for token in ("公园", "湿地", "自然"))
    is_night = any(token in f"{poi_type} {poi_name} {title}" for token in ("夜景", "商圈", "步行街", "购物"))

    if is_food:
        queries = [
            f"{poi_name} {city}",
            f"{city} local food",
            f"{city} breakfast" if "早餐" in f"{activity_type} {title}" else f"{city} restaurant",
            poi_name,
        ]
    elif is_hotel:
        queries = [
            f"{poi_name} {city}",
            f"{city} hotel",
            f"{city} boutique hotel",
            poi_name,
        ]
    elif is_park:
        queries = [
            f"{poi_name} {city}",
            f"{city} park",
            poi_name,
        ]
    elif is_night:
        queries = [
            f"{poi_name} {city}",
            f"{city} skyline",
            f"{city} night view",
        ]
    else:
        queries = [
            f"{poi_name} {city}",
            poi_name,
        ]

    if simple_type and len(simple_type) <= 12:
        queries.append(f"{city} {simple_type}")
    if activity_type and not is_food and not is_hotel:
        queries.append(f"{city} {activity_type}")
    if title and len(title) <= 20:
        queries.append(f"{city} {title}")

    return dedupe([query for query in queries if query.strip()])


def resolve_unsplash_image(city: str, activity: Dict[str, Any], poi: Dict[str, Any]) -> Dict[str, str]:
    photo = search_best_photo(build_image_queries(city, activity, poi), per_query=6)
    if not photo:
        return {}
    return {
        "url": photo.get("url", ""),
        "description": photo.get("description", ""),
        "photographer": photo.get("photographer", ""),
        "source": photo.get("source", "unsplash"),
    }


def enrich_activity_with_poi(activity: Dict[str, Any], poi: Dict[str, Any], city: str) -> Dict[str, Any]:
    enriched = dict(activity)
    description = build_poi_story(city, activity, poi)
    poi_image = str(poi.get("image_url", "")).strip()
    image_info = {} if poi_image else resolve_unsplash_image(city, activity, poi)
    lat = poi.get("lat")
    lng = poi.get("lng")
    coordinates = None
    if lat is not None and lng is not None:
        try:
            coordinates = {"lat": float(lat), "lng": float(lng)}
        except Exception:
            coordinates = None
    poi_price = extract_price_amount(poi.get("price"))
    ticket_price = int(round(poi_price)) if poi_price > 0 else int(activity.get("ticket_price", 0) or 0)

    enriched.update(
        {
            "location": poi.get("name") or enriched.get("location"),
            "description": description,
            "coordinates": coordinates,
            "image": poi_image or image_info.get("url") or enriched.get("image"),
            "image_source": "amap" if poi_image else image_info.get("source", ""),
            "image_photographer": image_info.get("photographer", ""),
            "image_description": image_info.get("description", ""),
            "tips": poi.get("tips") or enriched.get("tips"),
            "transportation": enriched.get("transportation") or "地铁/步行",
            "address": poi.get("address", ""),
            "opening_hours": poi.get("opening_hours", ""),
            "ticket_price": ticket_price,
            "ticketLabel": f"门票 ¥{ticket_price}" if ticket_price > 0 else "门票 免费",
        }
    )
    return enriched


def extract_itinerary_data(raw_data: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_data, list):
        return raw_data
    if isinstance(raw_data, dict):
        for key in ("itinerary", "days", "plan", "data", "result"):
            value = raw_data.get(key)
            if isinstance(value, list):
                return value
    return []


def pick_fallback_location(
    state: Dict[str, Any],
    keywords: List[str],
    used_locations: set[str],
    default_value: str,
) -> str:
    keyword_text = " ".join(keywords)
    if any(token in keyword_text for token in ("餐饮", "小吃", "面馆", "早餐", "中餐", "美食")):
        candidate_groups = [
            state.get("food_candidates", []) or [],
            state.get("attraction_candidates", []) or [],
        ]
    else:
        candidate_groups = [
            state.get("attraction_candidates", []) or [],
            state.get("food_candidates", []) or [],
        ]

    for candidates in candidate_groups:
        for poi in candidates:
            name = str(poi.get("name", "")).strip()
            type_text = str(poi.get("type", ""))
            searchable = f"{name} {type_text}"
            if not name or name in used_locations or is_bad_poi(name, type_text):
                continue
            if is_generic_location(name, state["city"]):
                continue
            if any(keyword in searchable for keyword in keywords):
                used_locations.add(name)
                return name
    for candidates in candidate_groups:
        for poi in candidates:
            name = str(poi.get("name", "")).strip()
            type_text = str(poi.get("type", ""))
            if not name or name in used_locations or is_bad_poi(name, type_text):
                continue
            if is_generic_location(name, state["city"]):
                continue
            used_locations.add(name)
            return name
    return default_value


def pick_fallback_candidate(
    state: Dict[str, Any],
    keywords: List[str],
    used_locations: set[str],
    category: str = "attraction",
) -> Dict[str, Any] | None:
    if category == "food":
        candidate_groups = [state.get("food_candidates", []) or [], state.get("attraction_candidates", []) or []]
    elif category == "hotel":
        candidate_groups = [state.get("hotel_options", []) or []]
    else:
        candidate_groups = [state.get("attraction_candidates", []) or []]

    for candidates in candidate_groups:
        for poi in candidates:
            name = str(poi.get("name", "")).strip()
            type_text = str(poi.get("type", ""))
            searchable = f"{name} {type_text}"
            if not name or name in used_locations or is_bad_poi(name, type_text):
                continue
            if is_generic_location(name, state["city"]):
                continue
            if any(keyword in searchable for keyword in keywords):
                used_locations.add(name)
                return poi
    for candidates in candidate_groups:
        for poi in candidates:
            name = str(poi.get("name", "")).strip()
            type_text = str(poi.get("type", ""))
            if not name or name in used_locations or is_bad_poi(name, type_text):
                continue
            if is_generic_location(name, state["city"]):
                continue
            used_locations.add(name)
            return poi
    return None


def build_fallback_itinerary(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    city = state["city"]
    days = state["days"]
    preferences = state.get("preferences", [])
    start_date = state.get("start_date")
    hotel_options = state.get("hotel_options", []) or []
    hotel_name = str(hotel_options[0].get("name", "")).strip() if hotel_options else ""
    hotel_price = hotel_options[0].get("price") if hotel_options else ""
    hotel_address = str(hotel_options[0].get("address", "")).strip() if hotel_options else ""

    try:
        base_date = date.fromisoformat(start_date) if start_date else date.today()
    except Exception:
        base_date = date.today()

    pref_text = "、".join(preferences[:3]) if preferences else "城市经典"
    day_themes = [
        "地标与城市初印象",
        "历史文化深度体验",
        "自然与休闲漫游",
        "美食与夜生活探索",
        "艺术人文与街区巡游",
        "近郊轻户外与特色体验",
    ]
    fallback_location_rules = [
        ["餐饮", "小吃", "面馆", "早餐"],
        ["风景", "景点", "公园", "博物馆", "寺庙"],
        ["餐饮", "中餐", "美食"],
        ["博物馆", "历史", "文化", "景点"],
        ["公园", "湿地", "风景"],
        ["步行街", "商场", "购物", "夜景", "餐饮"],
    ]
    activity_blueprints = [
        ("08:30-10:00", "本地特色早餐开启行程", "美食餐饮", "本地早餐店", 60, 35, "优先选择本地人常去的早餐店，早点到店更顺畅。", "food"),
        ("10:00-12:00", "核心景点参观", "观光游览", "城市地标景区", 120, 90, "提前预约门票，减少排队时间。", "attraction"),
        ("12:30-13:30", "特色午餐", "美食餐饮", "热门餐厅聚集区", 60, 110, "可提前线上取号。", "food"),
        ("14:00-16:00", "博物馆/文化街区", "文化体验", "博物馆与历史街区", 120, 60, "馆内注意闭馆时间。", "attraction"),
        ("16:30-18:00", "城市公园散步", "户外活动", "城市公园", 90, 20, "适合拍照与休息。", "attraction"),
        ("19:00-21:00", "夜景与晚餐", "休闲放松", "夜景商圈", 120, 130, "夜间出行建议打车返程。", "food"),
    ]

    itinerary: List[Dict[str, Any]] = []
    used_locations: set[str] = set()
    for day_idx in range(days):
        current_date = (base_date + timedelta(days=day_idx)).isoformat()
        day_no = day_idx + 1
        theme = day_themes[day_idx % len(day_themes)]
        activities = []
        for slot_idx, blueprint in enumerate(activity_blueprints):
            time_slot, title, act_type, location, duration, cost, tips, category = blueprint
            candidate = pick_fallback_candidate(
                state,
                fallback_location_rules[slot_idx % len(fallback_location_rules)],
                used_locations,
                category=category,
            )
            resolved_location = str(candidate.get("name", "")).strip() if candidate else pick_fallback_location(
                state,
                fallback_location_rules[slot_idx % len(fallback_location_rules)],
                used_locations,
                f"{city}{location}",
            )
            transport = "地铁/步行/网约车组合"
            if hotel_name and slot_idx == 0:
                transport = f"从{hotel_name}出发，优先地铁或步行"
            base_activity = {
                "time": time_slot,
                "title": f"{title}（第{day_no}天）",
                "description": f"围绕{city}{pref_text}偏好安排，兼顾效率与体验。",
                "type": act_type,
                "location": resolved_location,
                "duration": duration,
                "cost_estimate": cost,
                "ticket_price": cost if any(keyword in act_type for keyword in ("观光", "文化", "户外")) else 0,
                "tips": tips,
                "transportation": transport,
            }
            if candidate:
                base_activity = enrich_activity_with_poi(base_activity, candidate, city)
                base_activity["duration"] = duration
                base_activity["cost_estimate"] = int(round(extract_price_amount(candidate.get("price")))) or cost
                base_activity["transportation"] = transport
                base_activity["tips"] = tips
            activities.append(base_activity)

        itinerary.append(
            {
                "day": day_no,
                "date": current_date,
                "theme": f"{city}·{theme}",
                "summary": f"第{day_no}天聚焦「{theme}」，活动更均衡，避免跨天重复。",
                "hotel_recommendation": {
                    "name": hotel_name or f"{city}精选酒店",
                    "price_estimate": hotel_price or "待查询",
                    "address": hotel_address or f"{city}市区",
                    "reason": "位置更适合作为本次路线的住宿落点，方便第二天继续出发。",
                },
                "activities": activities,
            }
        )
    return itinerary


def normalize_itinerary(itinerary: List[Dict[str, Any]], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    target_days = state["days"]
    city = state["city"]
    fallback_location_rules = [
        ["餐饮", "小吃", "面馆", "早餐"],
        ["风景", "景点", "公园", "博物馆", "寺庙"],
        ["餐饮", "中餐", "美食"],
        ["博物馆", "历史", "文化", "景点"],
        ["公园", "湿地", "风景"],
        ["步行街", "商场", "购物", "夜景", "餐饮"],
    ]
    if not itinerary:
        return build_fallback_itinerary(state)

    if len(itinerary) > target_days:
        itinerary = itinerary[:target_days]
    elif len(itinerary) < target_days:
        fallback = build_fallback_itinerary(state)
        itinerary.extend(fallback[len(itinerary):target_days])

    fallback_days = build_fallback_itinerary(state)
    used_locations = set()
    for idx, day in enumerate(itinerary):
        day["day"] = idx + 1
        day.setdefault("date", fallback_days[idx].get("date"))
        day.setdefault("theme", fallback_days[idx].get("theme"))
        day.setdefault("summary", fallback_days[idx].get("summary"))
        day.setdefault("hotel_recommendation", fallback_days[idx].get("hotel_recommendation"))
        activities = day.get("activities", [])
        if not isinstance(activities, list):
            activities = []

        for a_idx, act in enumerate(activities):
            if not isinstance(act, dict):
                continue
            act.setdefault("time", fallback_days[idx]["activities"][a_idx % len(fallback_days[idx]["activities"])]["time"])
            act.setdefault("title", f"第{idx + 1}天活动{a_idx + 1}")
            act.setdefault("description", f"围绕{city}核心体验安排。")
            act.setdefault("type", "观光游览")
            base_loc = act.get("location") or f"{city}推荐地点{idx + 1}-{a_idx + 1}"
            if is_generic_location(str(base_loc), city):
                base_loc = pick_fallback_location(
                    state,
                    fallback_location_rules[a_idx % len(fallback_location_rules)],
                    used_locations,
                    fallback_days[idx]["activities"][a_idx % len(fallback_days[idx]["activities"])]["location"],
                )
            unique_loc = base_loc
            if unique_loc in used_locations:
                unique_loc = pick_fallback_location(
                    state,
                    fallback_location_rules[a_idx % len(fallback_location_rules)],
                    used_locations,
                    fallback_days[idx]["activities"][a_idx % len(fallback_days[idx]["activities"])]["location"],
                )
            act["location"] = unique_loc
            used_locations.add(unique_loc)
            act.setdefault("duration", 90)
            act.setdefault("cost_estimate", 80)
            act.setdefault(
                "ticket_price",
                act.get("cost_estimate", 80) if any(keyword in str(act.get("type", "")) for keyword in ("观光", "文化", "户外")) else 0,
            )
            act.setdefault("tips", "建议提前查看开放时间。")
            act.setdefault("transportation", "地铁/步行")

        while len(activities) < 5:
            activities.append(fallback_days[idx]["activities"][len(activities) % len(fallback_days[idx]["activities"])])
        day["activities"] = activities[:6]

        if idx > 0 and day.get("theme") == itinerary[idx - 1].get("theme"):
            day["theme"] = f"{day.get('theme', city)}（第{idx + 1}天）"

    return itinerary


def build_local_summary(state: Dict[str, Any]) -> str:
    city = state["city"]
    days = state["days"]
    travelers = state.get("travelers", 1)
    budget = state.get("estimated_budget", {}).get("total", 0)
    plan = state.get("plan", [])
    poi_names: List[str] = []
    seen = set()
    for day in plan:
        for activity in day.get("activities", []):
            summary_text = " ".join(
                [
                    str(activity.get("title", "")),
                    str(activity.get("type", "")),
                    str(activity.get("description", "")),
                    str(activity.get("location", "")),
                ]
            )
            if any(token in summary_text for token in ("早餐", "午餐", "晚餐", "餐", "美食", "酒店", "宾馆", "民宿", "住宿")):
                continue
            location = str(activity.get("location", "")).strip()
            if not location or location in seen or is_generic_location(location, city) or is_bad_poi(location, str(activity.get("type", ""))):
                continue
            seen.add(location)
            poi_names.append(location)
            if len(poi_names) >= 8:
                break
        if len(poi_names) >= 8:
            break
    poi_text = "、".join(poi_names) if poi_names else "请在地图页查看景点详情"
    return (
        f"# {city} {days}天旅行计划\n\n"
        f"## 行程概览\n"
        f"- 目的地：{city}\n"
        f"- 天数：{days}天\n"
        f"- 人数：{travelers}人\n"
        f"- 预算估算：约{budget}元\n\n"
        f"## 重点景点\n"
        f"{poi_text}\n\n"
        "## 温馨提示\n"
        "请结合实时天气和景点开放时间，灵活调整每日节奏。"
    )


def extract_json_block(content: str) -> Dict[str, Any] | List[Dict[str, Any]] | None:
    try:
        return json.loads(content)
    except Exception:
        match = re.search(r"\{.*\}|\[.*\]", content, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except Exception:
            return None


def build_query_agent_fallback(state: Dict[str, Any]) -> Dict[str, Any]:
    city = state["city"]
    preferences = normalize_preferences(state.get("preferences", []) or [])
    budget = state.get("budget", "中等")
    preference_queries = {
        "culture": [f"{city}城市地标", f"{city}博物馆", f"{city}历史街区"],
        "food": [f"{city}本地特色早餐", f"{city}老字号早餐", f"{city}高评分特色餐厅"],
        "nature": [f"{city}自然地标", f"{city}湿地景区", f"{city}山海风景"],
        "shopping": [f"{city}人气步行街", f"{city}夜景地标", f"{city}商业街区"],
        "photography": [f"{city}城市地标", f"{city}夜景地标", f"{city}打卡景点"],
    }

    attraction_queries: List[str] = []
    for pref in preferences[:3]:
        attraction_queries.extend(preference_queries.get(pref, []))

    if not attraction_queries:
        attraction_queries = [f"{city}城市地标", f"{city}历史文化景点", f"{city}博物馆", f"{city}代表性街区", f"{city}夜景地标"]

    return {
        "travel_style": "城市深度体验",
        "planning_focus": f"围绕{city}的真实高评分景点、美食和休闲体验规划路线，优先减少跨城折返。",
        "attraction_queries": dedupe(attraction_queries),
        "hotel_queries": dedupe(
            [
                f"{city}交通便利酒店",
                f"{city}{budget}酒店",
                f"{city}高评分酒店",
            ]
        ),
        "must_have": ["真实景点", "本地美食", "休闲段落"],
    }


def score_general_candidate(poi: Dict[str, Any], city: str, query: str, hotel: bool = False) -> float:
    name = str(poi.get("name", ""))
    type_text = str(poi.get("type", ""))
    address = str(poi.get("address", ""))
    if is_bad_poi(name, type_text):
        return -10
    score = float(poi.get("rating", 0) or 0) * 2
    if poi.get("image_url"):
        score += 1.5
    if city and city in name:
        score += 0.5
    if city and city in address:
        score += 0.4
    if query and (query in name or query in type_text):
        score += 0.8
    if hotel:
        if "酒店" in name or "酒店" in type_text or "宾馆" in type_text:
            score += 3
    else:
        if "酒店" in name or "酒店" in type_text or "宾馆" in type_text:
            score -= 4
        searchable = f"{name} {type_text} {address}"
        query_is_food = any(text in query for text in ("早餐", "小吃", "餐厅", "美食", "饭店"))
        if not query_is_food and any(text in searchable for text in ("餐饮", "中餐", "快餐", "小吃", "面馆", "餐厅", "饭店")):
            score -= 4.5
        if any(text in type_text for text in ("风景", "景点", "博物馆", "餐饮", "购物", "古镇", "历史", "文化")):
            score += 1.2
        if "公园" in type_text and not any(text in query for text in ("公园", "湿地", "自然", "户外")):
            score -= 1.8
        if any(text in f"{name} {type_text}" for text in ("博物馆", "历史", "古镇", "老街", "景区", "风景名胜", "步行街", "城隍庙", "外滩")):
            score += 1.8
        if any(text in f"{name} {type_text}" for text in ("早餐", "面馆", "小吃", "老字号")) and any(text in query for text in ("早餐", "小吃", "餐厅", "美食")):
            score += 1.4
        if any(text in query for text in ("早餐", "小吃", "餐厅", "美食", "特色")):
            score += score_food_locality(searchable, city, query)
        if has_branch_marker(name):
            score -= 1.0
    return score


def collect_ranked_candidates(queries: List[str], city: str, hotel: bool = False, limit: int = 10) -> List[Dict[str, Any]]:
    ranked: List[tuple[float, Dict[str, Any]]] = []
    seen = set()
    for query in queries:
        variants = normalize_search_query(query, city) or [query]
        for variant in variants[:4]:
            try:
                pois = search_hotels(variant, city, 1, 8) if hotel else search_pois(variant, city, 1, 8)
            except Exception as exc:
                logger.warning("POI 搜索失败 query=%s city=%s error=%s", variant, city, exc)
                continue
            for poi in pois:
                name = str(poi.get("name", "")).strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                ranked.append((score_general_candidate(poi, city, variant, hotel=hotel), poi))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [poi for _, poi in ranked[:limit]]


def build_recommendation_from_candidates(
    city: str,
    title: str,
    rec_type: str,
    items: List[Dict[str, Any]],
    description: str,
) -> Dict[str, Any]:
    return {
        "type": rec_type,
        "title": title,
        "items": [str(item.get("name", "")).strip() for item in items if item.get("name")][:3],
        "description": description,
        "reasoning": f"已优先筛选{city}评分较高、图片更完整且更适合串联路线的真实地点。",
        "best_time": "全天",
        "price_range": "中等",
        "tips": "建议结合地图路线与开放时间使用，热门地点可提前预约。",
    }
