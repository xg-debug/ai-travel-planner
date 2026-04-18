import json
import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, List

from app.services.amap_service import search_hotels, search_pois
from app.services.unsplash_service import search_best_photo

logger = logging.getLogger(__name__)

GENERIC_LOCATION_PATTERNS = (
    "早餐店",
    "餐厅聚集区",
    "热门餐厅",
    "夜景商圈",
    "城市公园",
    "地标景区",
    "历史街区",
    "博物馆",
    "推荐地点",
)

POI_STORY_HINTS = {
    "西湖": "西湖是杭州最具代表性的城市名片，适合沿湖散步、乘船看景，也能串联断桥、白堤和孤山一线的人文景观。",
    "灵隐寺": "灵隐寺是杭州最重要的佛教古刹之一，飞来峰造像与古寺院落一起构成了很强的历史厚度与山林禅意。",
    "河坊街": "河坊街保留了杭州老城的市井气质，适合边走边逛小吃、手作与老字号店铺，感受南宋御街一带的烟火气。",
    "南宋御街": "南宋御街是老杭州城市肌理的代表片区，石板路、骑楼和老字号店铺很适合慢慢逛，感受历史街区氛围。",
    "西溪湿地": "西溪湿地以水网、芦苇与湿地生态著称，适合坐船、慢行和拍自然风景，整体节奏比市区更松弛。",
    "京杭大运河": "运河一线串起杭州近代商贸与漕运记忆，夜间灯光映在河面上很有层次，适合散步看夜景。",
    "湖滨步行街": "湖滨步行街兼顾西湖夜景、商业与餐饮，晚上灯光氛围好，适合作为收尾散步和吃晚饭的区域。",
    "太子湾公园": "太子湾公园以大草坪、曲水和季节花景见长，春季尤其适合拍照和散步，是杭州很受欢迎的城市公园。",
    "浙江省博物馆": "浙江省博物馆适合系统了解杭州与浙江的人文脉络，馆藏内容覆盖书画、陶瓷和地方历史。",
    "中国丝绸博物馆": "中国丝绸博物馆能把杭州与丝绸文化的联系讲得很完整，展陈兼具审美和历史信息。",
    "楼外楼": "楼外楼是杭州知名老字号，适合体验杭帮菜的经典做法，西湖醋鱼、东坡肉等传统菜式辨识度很高。",
    "新丰小吃": "新丰小吃是杭州本地人熟悉的早餐选择，包子、馄饨和豆浆出餐快，适合作为行程开始前的轻早餐。",
    "游埠豆浆": "游埠豆浆以豆浆、油条和烧饼等中式早餐组合受欢迎，适合快速感受杭州清晨的本地饮食节奏。",
    "菊英面馆": "菊英面馆是杭州口碑面馆之一，适合尝试片儿川等本地面食，风格朴实但很有城市日常感。",
    "绿茶餐厅": "绿茶餐厅以江南风格家常菜见长，环境轻松，适合作为中午或傍晚的稳定用餐选择。",
}


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
    if any(keyword in text for keyword in GENERIC_LOCATION_PATTERNS):
        return True
    if re.search(r"\d+-\d+$", text):
        return True
    if text.startswith(city) and any(keyword in text for keyword in GENERIC_LOCATION_PATTERNS):
        return True
    return False


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
        queries.extend(["杭帮菜", "特色餐厅", "人气餐厅"])
    elif "夜景" in hint_text or "商圈" in hint_text:
        queries.extend(["夜景", "夜游", "步行街"])
    elif "公园" in hint_text or "户外" in hint_text or "自然" in hint_text:
        queries.extend(["城市公园", "公园", "湿地公园"])
    elif "博物" in hint_text or "历史" in hint_text or "文化" in hint_text:
        queries.extend(["博物馆", "历史街区", "文化景点"])
    else:
        queries.extend(["地标景点", "经典景点", "热门景点"])

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
    type_text = str(poi.get("type", ""))

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


def build_poi_story(city: str, activity: Dict[str, Any], poi: Dict[str, Any]) -> str:
    name = str(poi.get("name", "")).strip()
    address = str(poi.get("address", city)).strip()
    for pattern, story in POI_STORY_HINTS.items():
        if pattern in name:
            return f"{name}值得安排这一站，{story} 建议结合周边步行慢逛，更能感受到现场氛围。"

    hint_text = " ".join(
        [
            str(activity.get("title", "")),
            str(activity.get("type", "")),
            str(activity.get("description", "")),
            str(activity.get("location", "")),
        ]
    )

    if "早餐" in hint_text:
        return f"{name}是{city}适合清晨打卡的早餐选择，出餐通常比较快，能先尝到当地日常口味，再顺路开启当天行程。"
    if "午餐" in hint_text or "晚餐" in hint_text or "餐" in hint_text:
        return f"{name}适合作为当天的正餐落点，通常能吃到更有地方特色的菜式，安排在逛景点之间也比较顺路。"
    if "夜景" in hint_text or "商圈" in hint_text:
        return f"{name}适合放在傍晚到夜间，灯光、街区氛围和餐饮选择会更完整，边逛边吃更能感受到{city}夜生活。"
    if "公园" in hint_text or "户外" in hint_text or "自然" in hint_text:
        return f"{name}适合留出一段慢节奏时间散步休息，现场通常比照片更舒服，也方便拍照和调整体力。"
    if "博物" in hint_text or "文化" in hint_text or "历史" in hint_text:
        return f"{name}适合作为了解{city}人文历史的一站，慢慢看展或逛街区，会比单纯打卡更有收获。"
    return f"{name}位于{address}，适合作为当天路线中的重点停留点，兼顾拍照、步行体验和城市氛围。"


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
    image_info = resolve_unsplash_image(city, activity, poi)
    lat = poi.get("lat")
    lng = poi.get("lng")
    coordinates = None
    if lat is not None and lng is not None:
        try:
            coordinates = {"lat": float(lat), "lng": float(lng)}
        except Exception:
            coordinates = None

    enriched.update(
        {
            "location": poi.get("name") or enriched.get("location"),
            "description": description,
            "coordinates": coordinates,
            "image": image_info.get("url") or poi.get("image_url") or enriched.get("image"),
            "image_source": image_info.get("source", "amap" if poi.get("image_url") else ""),
            "image_photographer": image_info.get("photographer", ""),
            "image_description": image_info.get("description", ""),
            "tips": poi.get("tips") or enriched.get("tips"),
            "transportation": enriched.get("transportation") or "地铁/步行",
            "address": poi.get("address", ""),
            "opening_hours": poi.get("opening_hours", ""),
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
    candidates = state.get("attraction_candidates", []) or []
    for poi in candidates:
        name = str(poi.get("name", "")).strip()
        type_text = str(poi.get("type", ""))
        searchable = f"{name} {type_text}"
        if not name or name in used_locations:
            continue
        if any(keyword in searchable for keyword in keywords):
            used_locations.add(name)
            return name
    for poi in candidates:
        name = str(poi.get("name", "")).strip()
        if name and name not in used_locations:
            used_locations.add(name)
            return name
    return default_value


def build_fallback_itinerary(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    city = state["city"]
    days = state["days"]
    preferences = state.get("preferences", [])
    start_date = state.get("start_date")
    hotel_options = state.get("hotel_options", []) or []
    hotel_name = str(hotel_options[0].get("name", "")).strip() if hotel_options else ""

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
        ("08:30-10:00", "酒店周边早餐与出发", "美食餐饮", "本地早餐店", 60, 35, "避开通勤高峰，优先地铁出行。"),
        ("10:00-12:00", "核心景点参观", "观光游览", "城市地标景区", 120, 90, "提前预约门票，减少排队时间。"),
        ("12:30-13:30", "特色午餐", "美食餐饮", "热门餐厅聚集区", 60, 110, "可提前线上取号。"),
        ("14:00-16:00", "博物馆/文化街区", "文化体验", "博物馆与历史街区", 120, 60, "馆内注意闭馆时间。"),
        ("16:30-18:00", "城市公园散步", "户外活动", "城市公园", 90, 20, "适合拍照与休息。"),
        ("19:00-21:00", "夜景与晚餐", "休闲放松", "夜景商圈", 120, 130, "夜间出行建议打车返程。"),
    ]

    itinerary: List[Dict[str, Any]] = []
    used_locations: set[str] = set()
    for day_idx in range(days):
        current_date = (base_date + timedelta(days=day_idx)).isoformat()
        day_no = day_idx + 1
        theme = day_themes[day_idx % len(day_themes)]
        activities = []
        for slot_idx, blueprint in enumerate(activity_blueprints):
            time_slot, title, act_type, location, duration, cost, tips = blueprint
            resolved_location = pick_fallback_location(
                state,
                fallback_location_rules[slot_idx % len(fallback_location_rules)],
                used_locations,
                f"{city}{location}{day_no}-{slot_idx + 1}",
            )
            transport = "地铁/步行/网约车组合"
            if hotel_name and slot_idx == 0:
                transport = f"从{hotel_name}出发，优先地铁或步行"
            activities.append(
                {
                    "time": time_slot,
                    "title": f"{title}（第{day_no}天）",
                    "description": f"围绕{city}{pref_text}偏好安排，兼顾效率与体验。",
                    "type": act_type,
                    "location": resolved_location,
                    "duration": duration,
                    "cost_estimate": cost,
                    "tips": tips,
                    "transportation": transport,
                }
            )

        itinerary.append(
            {
                "day": day_no,
                "date": current_date,
                "theme": f"{city}·{theme}",
                "summary": f"第{day_no}天聚焦「{theme}」，活动更均衡，避免跨天重复。",
                "activities": activities,
            }
        )
    return itinerary


def normalize_itinerary(itinerary: List[Dict[str, Any]], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    target_days = state["days"]
    city = state["city"]
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
            unique_loc = base_loc
            if unique_loc in used_locations:
                unique_loc = f"{base_loc}{idx + 1}-{a_idx + 1}"
            act["location"] = unique_loc
            used_locations.add(unique_loc)
            act.setdefault("duration", 90)
            act.setdefault("cost_estimate", 80)
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
            location = str(activity.get("location", "")).strip()
            if not location or location in seen:
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
    preferences = state.get("preferences", []) or []
    budget = state.get("budget", "中等")
    preference_queries = {
        "culture": [f"{city}历史文化景点", f"{city}博物馆", f"{city}历史街区"],
        "food": [f"{city}本地早餐", f"{city}杭帮菜", f"{city}高评分餐厅"],
        "nature": [f"{city}城市公园", f"{city}湿地公园", f"{city}自然风景"],
        "shopping": [f"{city}步行街", f"{city}夜景商圈", f"{city}商业街"],
        "photography": [f"{city}夜景", f"{city}观景点", f"{city}打卡景点"],
    }

    attraction_queries: List[str] = []
    for pref in preferences[:3]:
        attraction_queries.extend(preference_queries.get(pref, []))

    if not attraction_queries:
        attraction_queries = [f"{city}热门景点", f"{city}历史文化景点", f"{city}高评分餐厅", f"{city}城市公园"]

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
    score = float(poi.get("rating", 0) or 0) * 2
    if poi.get("image_url"):
        score += 1.5
    if city and city in name:
        score += 0.5
    if query and (query in name or query in type_text):
        score += 0.8
    if hotel:
        if "酒店" in name or "酒店" in type_text or "宾馆" in type_text:
            score += 3
    else:
        if "酒店" in name or "酒店" in type_text or "宾馆" in type_text:
            score -= 4
        if any(text in type_text for text in ("风景", "景点", "公园", "博物馆", "餐饮", "购物")):
            score += 1.2
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
