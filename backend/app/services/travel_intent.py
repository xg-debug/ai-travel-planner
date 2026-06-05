import re
from typing import Dict


GENERIC_DESTINATION_TERMS = {
    "周边",
    "附近",
    "城市",
    "景点",
    "路线",
    "旅游",
    "旅行",
    "游玩",
    "目的地",
    "海边",
    "沙滩",
    "草原",
    "雪山",
    "古镇",
    "山区",
    "海岛",
    "温泉",
}

INTENT_WORDS = "我|想|要|准备|计划|打算|去|到|玩|游|逛|看|吃|住|出发|返回|返程|预算|人均|天|日"


def _normalize_input(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip().rstrip("!?！？。；;,，、")


def _strip_administrative_suffix(value: str) -> str:
    text = str(value or "").strip()
    while True:
        next_text = re.sub(r"(特别行政区|自治区|自治州|地区|城市|市|省|县|区)$", "", text)
        if next_text == text:
            return text
        text = next_text


def _clean_destination_candidate(value: str) -> str:
    text = _strip_administrative_suffix(_normalize_input(value))
    text = re.sub(r"^(?:想去|想要去|计划去|准备去|打算去|前往|目的地是|目的地为|目的地|去|到)", "", text)
    text = re.sub(r"(?:旅游|旅行|游玩|自由行|攻略|路线|行程|[0-9一二三四五六七八九十两]+日游)$", "", text)
    return _strip_administrative_suffix(text)


def _is_valid_destination(value: str) -> bool:
    text = _clean_destination_candidate(value)
    return bool(text and len(text) >= 2 and text not in GENERIC_DESTINATION_TERMS)


def _looks_like_plain_destination(value: str) -> bool:
    cleaned = _normalize_input(value)
    if not re.fullmatch(r"[\u4e00-\u9fa5A-Za-z·路]{2,24}", cleaned):
        return False
    return not re.search(INTENT_WORDS, cleaned)


def _extract_destination_by_pattern(text: str) -> str:
    patterns = (
        r"(?:从|自)[\u4e00-\u9fa5A-Za-z·路]{2,24}(?:出发|启程|动身)(?:到|去|前往)([\u4e00-\u9fa5A-Za-z·路]{2,24})",
        r"(?:目的地(?:是|为)?|想去|想要去|计划去|准备去|打算去|前往|去|到)([\u4e00-\u9fa5A-Za-z·路]{2,24})",
        r"([\u4e00-\u9fa5A-Za-z·路]{2,24})(?:[0-9一二三四五六七八九十两]+日游|旅游|旅行|游玩|自由行|攻略)",
    )
    for pattern in patterns:
        for matched in re.finditer(pattern, text):
            destination = _clean_destination_candidate(matched.group(1))
            if _is_valid_destination(destination):
                return destination
    return ""


def parse_travel_intent(value: str) -> Dict[str, str]:
    cleaned = _normalize_input(value)
    if not cleaned:
        return {"destination": "", "additional_requirements": ""}

    exact_destination = _strip_administrative_suffix(cleaned)
    if _looks_like_plain_destination(cleaned):
        return {"destination": exact_destination, "additional_requirements": ""}

    destination = _extract_destination_by_pattern(cleaned)
    return {
        "destination": destination,
        "additional_requirements": cleaned if destination and destination != cleaned else "",
    }


def normalize_trip_city_and_query(city: str, query: str) -> Dict[str, str]:
    raw_city = str(city or "").strip()
    raw_query = str(query or "").strip()
    city_only = parse_travel_intent(raw_city)
    normalized_city = city_only["destination"]

    if not normalized_city and raw_city and _looks_like_plain_destination(raw_city):
        normalized_city = _strip_administrative_suffix(_normalize_input(raw_city))

    if not normalized_city:
        normalized_city = parse_travel_intent(raw_query)["destination"]

    normalized_query = raw_query
    if normalized_city and normalized_query and normalized_city not in normalized_query:
        normalized_query = "，".join([normalized_query, normalized_city])
    elif normalized_city and not normalized_query:
        normalized_query = normalized_city

    return {
        "city": normalized_city,
        "query": normalized_query,
    }
