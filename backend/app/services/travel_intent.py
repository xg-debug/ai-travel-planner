import re
from typing import Dict


CITY_DESTINATIONS = sorted(
    {
        "北京",
        "上海",
        "广州",
        "深圳",
        "杭州",
        "南京",
        "苏州",
        "成都",
        "重庆",
        "武汉",
        "西安",
        "长沙",
        "青岛",
        "厦门",
        "福州",
        "泉州",
        "宁波",
        "温州",
        "无锡",
        "常州",
        "扬州",
        "南通",
        "天津",
        "大连",
        "沈阳",
        "哈尔滨",
        "长春",
        "济南",
        "烟台",
        "威海",
        "郑州",
        "洛阳",
        "开封",
        "太原",
        "石家庄",
        "合肥",
        "南昌",
        "昆明",
        "大理",
        "丽江",
        "西双版纳",
        "贵阳",
        "遵义",
        "南宁",
        "桂林",
        "北海",
        "海口",
        "三亚",
        "拉萨",
        "林芝",
        "西宁",
        "兰州",
        "敦煌",
        "银川",
        "呼和浩特",
        "乌鲁木齐",
        "喀什",
        "香港",
        "澳门",
        "台北",
        "高雄",
        "垦丁",
        "舟山",
        "黄山",
        "婺源",
        "张家界",
        "凤凰",
        "恩施",
        "宜昌",
        "九江",
        "景德镇",
        "秦皇岛",
        "承德",
        "阿勒泰",
        "伊犁",
        "吐鲁番",
        "呼伦贝尔",
        "漠河",
        "延吉",
        "长白山",
    },
    key=len,
    reverse=True,
)

REGION_DESTINATIONS = sorted(
    {
        "广东",
        "浙江",
        "江苏",
        "四川",
        "云南",
        "贵州",
        "广西",
        "海南",
        "福建",
        "山东",
        "河南",
        "河北",
        "湖北",
        "湖南",
        "江西",
        "安徽",
        "陕西",
        "山西",
        "甘肃",
        "青海",
        "宁夏",
        "新疆",
        "西藏",
        "内蒙古",
        "东北",
        "华东",
        "川西",
    },
    key=len,
    reverse=True,
)

GENERIC_DESTINATIONS = {
    "海边",
    "沙滩",
    "草原",
    "雪山",
    "古镇",
    "山里",
    "海岛",
    "温泉",
    "景点",
    "城市",
    "周边",
}


def _normalize_input(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip().rstrip("!?！？。；;")


def _strip_administrative_suffix(value: str) -> str:
    return re.sub(r"(特别行政区|自治区|自治州|地区|市|省|县|区)$", "", value)


def _find_known_destination(text: str) -> str:
    for item in CITY_DESTINATIONS:
        if item in text:
            return item
    for item in REGION_DESTINATIONS:
        if item in text:
            return item
    return ""


def _extract_destination_by_pattern(text: str) -> str:
    patterns = (
        r"(?:想去|要去|准备去|计划去|打算去|一个人去|和.+?去|去|到|前往)([\u4e00-\u9fa5]{2,12}?)(?:旅游|旅行|游玩|玩|逛|看|吃|住|，|,|。|\.|、|和|并|$)",
        r"([\u4e00-\u9fa5]{2,12}?)(?:旅游|旅行|[0-9一二三四五六七八九十]+日游)",
    )
    for pattern in patterns:
        matched = re.search(pattern, text)
        destination = _strip_administrative_suffix(matched.group(1) if matched else "")
        if destination and destination not in GENERIC_DESTINATIONS:
            return destination
    return ""


def parse_travel_intent(value: str) -> Dict[str, str]:
    cleaned = _normalize_input(value)
    if not cleaned:
        return {"destination": "", "additional_requirements": ""}

    exact_destination = _strip_administrative_suffix(cleaned)
    if re.fullmatch(r"[\u4e00-\u9fa5A-Za-z·]{2,20}", cleaned) and not re.search(
        r"[我想要准备计划打算去到玩游逛看吃住，,、]", cleaned
    ):
        return {"destination": exact_destination, "additional_requirements": ""}

    destination = _find_known_destination(cleaned) or _extract_destination_by_pattern(cleaned)
    return {
        "destination": destination,
        "additional_requirements": cleaned if destination and destination != cleaned else "",
    }


def normalize_trip_city_and_query(city: str, query: str) -> Dict[str, str]:
    raw_city = str(city or "").strip()
    raw_query = str(query or "").strip()
    parsed = parse_travel_intent(f"{raw_city}，{raw_query}")
    city_only = parse_travel_intent(raw_city)
    normalized_city = parsed["destination"] or city_only["destination"]
    normalized_query = raw_query

    if parsed["additional_requirements"] and raw_city and raw_city not in raw_query:
        normalized_query = "，".join([item for item in (raw_query, raw_city) if item])

    return {
        "city": normalized_city,
        "query": normalized_query,
    }
