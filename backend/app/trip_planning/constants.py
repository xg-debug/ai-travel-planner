"""Shared constants for trip planning — single source of truth.

All hardcoded travel-domain token sets, distance thresholds, and financial
defaults live here so they can be tuned in one place.
"""

import re

# ---- Distance thresholds (km) ----
MAX_REASONABLE_LEG_KM = 18.0      # single leg longer than this is flagged
MAX_REASONABLE_DAY_KM = 45.0      # total daily distance beyond this is flagged
OUTLIER_DISTANCE_KM = 16.0        # cluster centroid → outlier threshold
DINNER_HOTEL_MAX_KM = 10.0        # dinner should be within this of hotel
CLOSING_HOTEL_MAX_KM = 18.0       # last activity should be within this of hotel
MEAL_ROUTE_MAX_KM = 12.0          # intermediate meal should be within this of route anchor

# ---- Activity classification tokens ----
HOTEL_ACTIVITY_TOKENS = ("入住", "办理入住", "酒店休息", "返回酒店", "回酒店", "住宿", "check-in", "check in")
TRANSPORT_TITLE_TOKENS = ("前往", "驱车", "打车", "乘车", "坐车", "自驾", "抵达", "出发", "返程", "返回", "上岛", "离岛", "交通", "路线")
RETURN_TERMINAL_TOKENS = ("返程", "返回", "回程", "离开", "回到出发地", "返回出发地", "返抵", "返家")
RETURN_TRANSPORT_TOKENS = ("高铁", "动车", "火车", "飞机", "航班", "机场", "车站", "大巴", "客运", "铁路", "交通")
INTERCITY_ACTIVITY_TOKENS = ("城际交通", "大交通", "往返交通", "去程交通", "返程交通")
DAYTIME_POI_TOKENS = ("博物馆", "纪念馆", "展览馆", "展馆", "美术馆", "科技馆", "文化馆", "图书馆", "故居", "会馆", "祠堂", "寺", "塔")
NIGHT_SAFE_TOKENS = ("夜景", "夜市", "步行街", "商圈", "酒吧", "演出", "灯光", "广场", "江景", "河景", "散步")
EVENING_ACTIVITY_TOKENS = ("夜", "晚间", "夜景", "夜市", "演出", "灯光", "酒吧", "散步")
FOOD_TOKENS = ("早餐", "早午茶", "午餐", "晚餐", "餐", "美食", "小吃", "咖啡", "茶", "火锅", "面", "饭")
ACTIVITY_WORDS = ("探索", "探秘", "攀登", "登高", "瞻仰", "漫步", "扫街", "打卡", "体验", "游览", "观光", "轻徒步", "徒步", "咖啡时光", "夜市扫街", "外观光")

# ---- Pre-compiled regex patterns for token matching ----
def _build_pattern(tokens):
    escaped = sorted((re.escape(t) for t in tokens), key=len, reverse=True)
    return re.compile("|".join(escaped))

RE_HOTEL_ACTIVITY = _build_pattern(HOTEL_ACTIVITY_TOKENS)
RE_TRANSPORT_TITLE = _build_pattern(TRANSPORT_TITLE_TOKENS)
RE_RETURN_TERMINAL = _build_pattern(RETURN_TERMINAL_TOKENS)
RE_RETURN_TRANSPORT = _build_pattern(RETURN_TRANSPORT_TOKENS)
RE_INTERCITY_ACTIVITY = _build_pattern(INTERCITY_ACTIVITY_TOKENS)
RE_DAYTIME_POI = _build_pattern(DAYTIME_POI_TOKENS)
RE_NIGHT_SAFE = _build_pattern(NIGHT_SAFE_TOKENS)
RE_EVENING_ACTIVITY = _build_pattern(EVENING_ACTIVITY_TOKENS)
RE_FOOD = _build_pattern(FOOD_TOKENS)
RE_ACTIVITY_WORDS = _build_pattern(ACTIVITY_WORDS)

# ---- Weather impact markers (used by weather_impact.py) ----
RAIN_MARKERS = ("雨", "雷", "阵雨", "暴雨")
SNOW_MARKERS = ("雪",)
FOG_MARKERS = ("雾", "霾")
OUTDOOR_MARKERS = ("公园", "海", "山", "湾", "湖", "河", "风景", "户外", "沙滩", "步道", "广场")
INDOOR_MARKERS = ("博物", "美术", "展", "馆", "商场", "购物", "餐", "咖啡", "书店")

RE_RAIN = _build_pattern(RAIN_MARKERS)
RE_SNOW = _build_pattern(SNOW_MARKERS)
RE_FOG = _build_pattern(FOG_MARKERS)
RE_OUTDOOR = _build_pattern(OUTDOOR_MARKERS)
RE_INDOOR = _build_pattern(INDOOR_MARKERS)

# ---- Budget defaults (per person / day, CNY) ----
BUDGET_LEVELS = {
    "经济": {"accommodation": 150, "food": 100, "transportation": 50, "tickets": 50, "shopping": 50},
    "中等": {"accommodation": 300, "food": 150, "transportation": 100, "tickets": 100, "shopping": 100},
    "豪华": {"accommodation": 800, "food": 300, "transportation": 200, "tickets": 200, "shopping": 200},
}

ACTIVITY_COST_FACTORS = {
    "观光": 1.0, "文化": 1.2, "美食": 1.5, "购物": 2.0,
    "娱乐": 1.8, "户外": 1.3, "休闲": 1.1, "交通": 0.8,
}

# ---- Scoring weights ----
ATTRACTION_WEIGHTS = {"preference": 0.30, "route": 0.25, "poi_quality": 0.20, "weather": 0.15, "budget": 0.10}
FOOD_WEIGHTS = {"local_feature": 0.30, "route": 0.25, "poi_quality": 0.20, "budget": 0.15, "preference": 0.10}
HOTEL_WEIGHTS = {"location": 0.35, "budget": 0.25, "poi_quality": 0.20, "route_connection": 0.15, "preference": 0.05}

# Dynamic weight adjustments per preference. Positive deltas boost the factor.
PREFERENCE_WEIGHT_MODIFIERS = {
    "classic": {"preference": 0.08, "route": 0.03},
    "food": {"local_feature": 0.10, "preference": 0.05},
    "local": {"preference": 0.05, "route": -0.05},
    "photo": {"poi_quality": 0.05, "weather": 0.08},
    "shopping": {"budget": 0.05, "route": 0.03},
    "citywalk": {"route": 0.08, "location": 0.05},
    "nature": {"weather": 0.10, "route": -0.03},
    "art": {"preference": 0.05, "weather": 0.05},
    "history": {"preference": 0.08, "poi_quality": 0.03},
}

PREFERENCE_KEYWORDS = {
    "classic": ("经典", "地标", "景点", "公园", "广场", "古城", "名胜"),
    "food": ("餐", "美食", "小吃", "咖啡", "茶", "夜市", "老字号"),
    "local": ("本地", "小众", "街区", "社区", "市集"),
    "photo": ("拍照", "摄影", "夜景", "海", "湾", "公园", "观景"),
    "shopping": ("购物", "商场", "商圈", "步行街", "市集"),
    "citywalk": ("街区", "步行街", "公园", "广场", "citywalk", "历史街区"),
    "nature": ("自然", "公园", "海", "湾", "山", "湖", "风景", "绿道"),
    "art": ("艺术", "美术", "展", "馆", "剧场", "文化"),
    "history": ("历史", "古", "博物", "纪念", "遗址", "文化"),
}

# Pre-compiled preference keyword regexes
RE_PREFERENCE_KEYWORDS = {k: _build_pattern(v) for k, v in PREFERENCE_KEYWORDS.items()}

# ---- Transport mode estimation ----
TRANSPORT_MODE_RULES = [
    (80, "城际汽车/市域交通", lambda d: max(30, d * 0.6)),
    (650, "高铁/动车", lambda d: 40 + d * 0.48),
    (1200, "高铁", lambda d: 70 + d * 0.52),
    (float("inf"), "飞机/高铁", lambda d: 280 + d * 0.62),
]

DEFAULT_MODE_DURATIONS = {
    "飞机": 180, "高铁": 420, "高铁/动车": 420, "火车": 720,
    "自驾": 600, "汽车": 240, "城际汽车/市域交通": 240,
}
