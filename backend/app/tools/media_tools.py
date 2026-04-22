from typing import Any, Dict, List

from app.services.unsplash_service import search_best_photo


def search_photo_tool(queries: List[str], per_query: int = 6) -> Dict[str, Any]:
    return search_best_photo(queries, per_query=per_query) or {}

