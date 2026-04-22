import re
from typing import Iterable, Tuple

GENERIC_LOCATION_KEYWORDS: Tuple[str, ...] = (
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

LOCAL_FOOD_HINTS: Tuple[str, ...] = (
    "本地",
    "特色",
    "传统",
    "地道",
    "老字号",
    "风味",
    "名吃",
    "非遗",
    "小吃",
    "早点",
    "早餐",
    "早茶",
    "面馆",
    "菜馆",
    "食府",
    "饭店",
)

CHAIN_BRAND_HINTS: Tuple[str, ...] = (
    "麦当劳",
    "肯德基",
    "星巴克",
    "瑞幸",
    "汉堡王",
    "必胜客",
    "德克士",
    "华莱士",
    "奈雪",
    "喜茶",
    "海底捞",
    "方中山",
)

NON_DESTINATION_CUISINE_HINTS: Tuple[str, ...] = (
    "新疆菜",
    "东北菜",
    "西北菜",
    "川菜",
    "湘菜",
    "黔菜",
    "滇菜",
    "云南菜",
    "湖北菜",
    "江西菜",
    "陕西菜",
    "兰州拉面",
    "胡辣汤",
    "螺蛳粉",
    "羊肉泡馍",
    "肉夹馍",
)


def contains_any(text: str, keywords: Iterable[str]) -> bool:
    searchable = str(text or "")
    return any(keyword in searchable for keyword in keywords)


def has_branch_marker(text: str) -> bool:
    searchable = str(text or "")
    return bool(re.search(r"(旗舰店|总店|分店|[一二三四五六七八九十\d]+店)", searchable))


def get_generic_location_keywords() -> Tuple[str, ...]:
    return GENERIC_LOCATION_KEYWORDS


def score_food_locality(searchable: str, city: str, query: str) -> float:
    score = 0.0
    text = str(searchable or "")
    query_text = str(query or "")

    if city and city in text:
        score += 1.6
    if contains_any(text, LOCAL_FOOD_HINTS):
        score += 1.8
    if contains_any(text, CHAIN_BRAND_HINTS):
        score -= 2.6
    if has_branch_marker(text):
        score -= 1.2

    if contains_any(query_text, ("早餐", "小吃", "餐厅", "美食", "特色", "本地")):
        if contains_any(text, ("餐饮", "中餐", "面馆", "小吃", "早茶", "饭店", "食府")):
            score += 0.8
        if contains_any(text, NON_DESTINATION_CUISINE_HINTS) and not contains_any(text, (city, "胡辣汤", "水席")):
            score -= 1.4

    return score
