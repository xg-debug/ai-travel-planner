import logging
from typing import Any, Dict, List

from app.agents.shared import (
    build_poi_queries,
    enrich_activity_with_poi,
    pick_best_poi,
)
from app.services.amap_service import search_pois

logger = logging.getLogger(__name__)


def poi_detail_agent_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """POI细节补全 agent：补齐坐标、图片和地点故事。"""
    logger.info("Fetching POI data for %s", state["city"])

    plan = state.get("plan", [])
    city = state["city"]
    poi_data = {}
    used_poi_names: set[str] = set()
    used_image_urls: set[str] = set()
    enriched_plan: List[Dict[str, Any]] = []

    for day in plan:
        next_day = {**day, "activities": []}
        for activity in day.get("activities", []):
            next_activity = dict(activity)
            location = str(activity.get("location", "")).strip()
            candidates: List[Dict[str, Any]] = []

            try:
                for query in build_poi_queries(next_activity, city)[:4]:
                    pois = search_pois(query, city, 1, 8)
                    if pois:
                        candidates.extend(pois)
            except Exception as exc:
                logger.error("Error fetching POI for %s: %s", location or city, exc)

            selected_poi = pick_best_poi(candidates, next_activity, city, used_poi_names)
            if selected_poi:
                used_poi_names.add(str(selected_poi.get("name", "")))
                next_activity = enrich_activity_with_poi(next_activity, selected_poi, city)
                image_url = str(next_activity.get("image", "")).strip()
                if image_url and image_url in used_image_urls:
                    next_activity["image"] = ""
                elif image_url:
                    used_image_urls.add(image_url)
                poi_name = str(selected_poi.get("name", "")).strip()
                enriched_poi = {**selected_poi}
                if next_activity.get("image"):
                    enriched_poi["image_url"] = next_activity.get("image")
                if next_activity.get("description"):
                    enriched_poi["description"] = next_activity.get("description")
                if poi_name:
                    poi_data[poi_name] = enriched_poi
                if location and location != poi_name:
                    poi_data[location] = enriched_poi

            next_day["activities"].append(next_activity)
        enriched_plan.append(next_day)

    logger.info("Fetched %s POIs", len(poi_data))
    return {"plan": enriched_plan, "poi_data": poi_data}
