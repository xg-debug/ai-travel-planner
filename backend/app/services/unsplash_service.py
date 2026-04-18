import logging
import re
from typing import Any, Dict, List, Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


def _dedupe(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


class UnsplashService:
    """Unsplash 图片服务。"""

    def __init__(self, access_key: Optional[str], secret_key: Optional[str] = None):
        self.access_key = access_key
        self.secret_key = secret_key
        self.base_url = "https://api.unsplash.com"
        self.disabled_reason: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept-Version": "v1",
                "Authorization": f"Client-ID {self.access_key}" if self.access_key else "",
            }
        )

    def _normalize_query(self, query: str) -> str:
        text = str(query or "").strip()
        text = re.sub(r"[（(].*?[)）]", " ", text)
        text = text.replace(";", " ")
        text = re.sub(r"\b(店|分店|店铺|旗舰店)\b", " ", text)
        text = re.sub(r"(餐饮服务|中餐厅|外国餐厅|快餐厅|住宿服务|宾馆酒店|风景名胜|公园广场)", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 48:
            text = text[:48].strip()
        return text

    def _expand_queries(self, queries: List[str]) -> List[str]:
        expanded: List[str] = []
        for query in queries:
            normalized = self._normalize_query(query)
            if not normalized:
                continue
            expanded.append(normalized)

            no_punct = re.sub(r"[()（）·,/，、]+", " ", normalized)
            no_punct = re.sub(r"\s+", " ", no_punct).strip()
            if no_punct and no_punct != normalized:
                expanded.append(no_punct)

            tokens = [token for token in re.split(r"\s+", no_punct) if token]
            if len(tokens) >= 2:
                expanded.append(" ".join(tokens[:2]))
                expanded.append(tokens[0])

        return _dedupe(expanded)

    def _extract_photo(self, result: Dict[str, Any], query: str) -> Dict[str, Any]:
        urls = result.get("urls", {})
        user = result.get("user", {})
        return {
            "url": urls.get("regular") or urls.get("small") or "",
            "description": result.get("description") or result.get("alt_description") or "",
            "photographer": user.get("name", ""),
            "source": "unsplash",
            "query": query,
            "width": result.get("width", 0),
            "height": result.get("height", 0),
            "likes": result.get("likes", 0),
            "tags": [tag.get("title", "") for tag in result.get("tags", []) if tag.get("title")],
        }

    def _score_photo(self, photo: Dict[str, Any], query: str) -> float:
        score = 0.0
        query_tokens = [token.lower() for token in re.split(r"\s+", query) if token]
        searchable = " ".join(
            [
                str(photo.get("description", "")),
                str(photo.get("photographer", "")),
                " ".join(photo.get("tags", [])),
            ]
        ).lower()

        likes = int(photo.get("likes", 0) or 0)
        width = int(photo.get("width", 0) or 0)
        height = int(photo.get("height", 0) or 0)

        score += min(likes, 2000) / 200
        if width >= 1000 and height >= 700:
            score += 2
        if width > 0 and height > 0:
            ratio = width / max(height, 1)
            if 1.1 <= ratio <= 2.2:
                score += 1.5

        for token in query_tokens:
            if token and token in searchable:
                score += 1.2

        if photo.get("description"):
            score += 0.5
        if photo.get("url"):
            score += 1
        return score

    def search_photos(self, query: str, per_page: int = 10) -> List[Dict[str, Any]]:
        """按关键词搜索图片。"""
        normalized_query = self._normalize_query(query)
        if not normalized_query or not self.access_key or self.disabled_reason:
            return []

        try:
            response = self.session.get(
                f"{self.base_url}/search/photos",
                params={
                    "query": normalized_query,
                    "per_page": per_page,
                    "orientation": "landscape",
                    "content_filter": "high",
                },
                timeout=10,
            )
            if response.status_code in {410, 422}:
                logger.warning("Unsplash 查询被拒绝，已跳过 query=%s status=%s", normalized_query, response.status_code)
                return []
            if response.status_code == 403:
                self.disabled_reason = "forbidden"
                logger.warning("Unsplash 已返回 403，当前进程内后续图片搜索将自动跳过")
                return []
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])
            photos = [self._extract_photo(result, normalized_query) for result in results]
            return [photo for photo in photos if photo.get("url")]
        except requests.Timeout:
            logger.warning("Unsplash 搜索超时 query=%s", normalized_query)
            return []
        except requests.exceptions.SSLError as exc:
            logger.warning("Unsplash SSL 异常 query=%s error=%s", normalized_query, exc)
            return []
        except Exception as exc:
            logger.warning("Unsplash 搜索失败 query=%s error=%s", normalized_query, exc)
            return []

    def search_best_photo(self, queries: List[str], per_query: int = 6) -> Optional[Dict[str, Any]]:
        """给一组候选查询词，返回最合适的一张图。"""
        expanded_queries = self._expand_queries(queries)
        if not expanded_queries:
            return None

        best_photo: Optional[Dict[str, Any]] = None
        best_score = -1.0

        for query in expanded_queries[:5]:
            photos = self.search_photos(query, per_page=per_query)
            for photo in photos:
                score = self._score_photo(photo, query)
                if score > best_score:
                    best_score = score
                    best_photo = photo

        return best_photo

    def get_photo_url(self, query: str) -> Optional[str]:
        """获取单张图片 URL。"""
        best_photo = self.search_best_photo([query], per_query=1)
        return best_photo.get("url") if best_photo else None


unsplash_service = UnsplashService(
    settings.UNSPLASH_ACCESS_KEY,
    settings.UNSPLASH_SECRET_KEY,
)


def search_photos(query: str, per_page: int = 10) -> List[Dict[str, Any]]:
    return unsplash_service.search_photos(query, per_page)


def search_best_photo(queries: List[str], per_query: int = 6) -> Optional[Dict[str, Any]]:
    return unsplash_service.search_best_photo(queries, per_query)


def get_photo_url(query: str) -> Optional[str]:
    return unsplash_service.get_photo_url(query)
