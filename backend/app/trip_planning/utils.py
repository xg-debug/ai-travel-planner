from __future__ import annotations

import json
import re
from typing import Any, List, Sequence


def dedupe(values: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def compact_name(value: Any, city: str = "") -> str:
    text = str(value or "").strip()
    if city:
        text = text.replace(city, "")
    return re.sub(r"[^\w\u4e00-\u9fff]", "", text).lower()


def extract_json_block(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    for candidate in (text, _slice_json_like(text)):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def _slice_json_like(text: str) -> str:
    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start >= 0 and end > start:
            return text[start : end + 1]
    return ""
