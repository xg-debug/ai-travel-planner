from __future__ import annotations

from typing import Dict

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.admin import RuntimeSetting


DEEPSEEK_FIXED_MODEL = "deepseek-v4-flash"

LLM_PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "api_key_setting": "llm.openai.api_key",
        "env_attr": "OPENAI_API_KEY",
        "default_model": settings.PROVIDER_DEFAULT_MODELS.get("openai", "gpt-4o-mini"),
    },
    "anthropic": {
        "label": "Anthropic",
        "api_key_setting": "llm.anthropic.api_key",
        "env_attr": "ANTHROPIC_API_KEY",
        "default_model": settings.PROVIDER_DEFAULT_MODELS.get("anthropic", "claude-sonnet-4-6"),
    },
    "google": {
        "label": "Google Gemini",
        "api_key_setting": "llm.google.api_key",
        "env_attr": "GOOGLE_API_KEY",
        "default_model": settings.PROVIDER_DEFAULT_MODELS.get("google", "gemini-2.5-flash"),
    },
    "deepseek": {
        "label": "DeepSeek",
        "api_key_setting": "llm.deepseek.api_key",
        "env_attr": "DEEPSEEK_API_KEY",
        "default_model": DEEPSEEK_FIXED_MODEL,
    },
}

MAP_PROVIDERS = {
    "amap_mcp_sse": {
        "label": "高德地图 MCP SSE",
        "api_key_setting": "map.amap_mcp.api_key",
        "env_attr": "AMAP_MCP_API_KEY",
    },
    "amap": {
        "label": "高德地图 REST",
        "api_key_setting": "map.amap.api_key",
        "env_attr": "AMAP_API_KEY",
    },
    "tencent": {
        "label": "腾讯位置服务",
        "api_key_setting": "map.tencent.api_key",
        "env_attr": "TENCENT_MAP_API_KEY",
    },
}


def mask_secret(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}****{text[-4:]}"


def is_present_secret(value: str | None) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    placeholders = (
        "your_openai_api_key_here",
        "your_openai_key",
        "your_anthropic_api_key_here",
        "your_anthropic_key",
        "your_google_api_key_here",
        "your_google_key",
        "your_deepseek_api_key_here",
        "your_deepseek_key",
        "your_amap_api_key_here",
        "your_amap_key",
        "your_amap_mcp_api_key_here",
        "your_amap_mcp_key",
        "your_tencent_map_api_key_here",
        "your_tencent_map_key",
    )
    placeholder_markers = (
        "your_",
        "replace_with_",
        "test_",
        "test-key",
        "demo_",
        "example_",
        "placeholder",
        "changeme",
    )
    return lowered not in placeholders and not any(marker in lowered for marker in placeholder_markers)


def get_setting_value(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.execute(select(RuntimeSetting).where(RuntimeSetting.setting_key == key)).scalar_one_or_none()
    if not row:
        return default
    return row.setting_value


def get_runtime_setting(key: str, default: str | None = None) -> str | None:
    db = SessionLocal()
    try:
        return get_setting_value(db, key, default)
    except SQLAlchemyError:
        return default
    finally:
        db.close()


def set_setting_value(db: Session, key: str, value: str, updated_by: str | None = None) -> RuntimeSetting:
    row = db.execute(select(RuntimeSetting).where(RuntimeSetting.setting_key == key)).scalar_one_or_none()
    if row:
        row.setting_value = value
        row.updated_by = updated_by
        db.add(row)
        return row
    row = RuntimeSetting(setting_key=key, setting_value=value, updated_by=updated_by)
    db.add(row)
    return row


def get_llm_provider(db: Session | None = None) -> str:
    provider = get_setting_value(db, "llm.provider") if db else get_runtime_setting("llm.provider")
    provider = (provider or settings.DEFAULT_LLM_PROVIDER or "deepseek").strip().lower()
    return provider if provider in LLM_PROVIDERS else "openai"


def normalize_llm_model(provider: str, model: str | None = None) -> str:
    if provider == "deepseek":
        return DEEPSEEK_FIXED_MODEL
    model = (model or "").strip()
    if model:
        return model
    return LLM_PROVIDERS.get(provider, LLM_PROVIDERS["openai"])["default_model"]


def get_llm_model(provider: str | None = None, db: Session | None = None) -> str:
    current_provider = provider or get_llm_provider(db)
    model = get_setting_value(db, "llm.model") if db else get_runtime_setting("llm.model")
    if model and model.strip():
        return normalize_llm_model(current_provider, model)
    if current_provider == settings.DEFAULT_LLM_PROVIDER and settings.DEFAULT_LLM_MODEL:
        return normalize_llm_model(current_provider, settings.DEFAULT_LLM_MODEL)
    return normalize_llm_model(current_provider)


def get_llm_api_key(provider: str, db: Session | None = None) -> str | None:
    meta = LLM_PROVIDERS.get(provider)
    if not meta:
        return None
    configured = get_setting_value(db, meta["api_key_setting"]) if db else get_runtime_setting(meta["api_key_setting"])
    return configured or getattr(settings, meta["env_attr"], None)


def get_map_provider(db: Session | None = None) -> str:
    provider = get_setting_value(db, "map.provider") if db else get_runtime_setting("map.provider")
    default_provider = settings.MAP_PROVIDER or ("amap_mcp_sse" if settings.AMAP_MCP_SSE_URL else "amap")
    provider = (provider or default_provider).strip().lower()
    return provider if provider in MAP_PROVIDERS else "amap"


def get_map_api_key(provider: str, db: Session | None = None) -> str | None:
    meta = MAP_PROVIDERS.get(provider)
    if not meta:
        return None
    configured = get_setting_value(db, meta["api_key_setting"]) if db else get_runtime_setting(meta["api_key_setting"])
    return configured or getattr(settings, meta["env_attr"], None)


def get_amap_mcp_sse_url(db: Session | None = None) -> str | None:
    configured = get_setting_value(db, "map.amap_mcp.sse_url") if db else get_runtime_setting("map.amap_mcp.sse_url")
    return configured or settings.AMAP_MCP_SSE_URL


def build_runtime_config_snapshot(db: Session) -> Dict[str, object]:
    llm_provider = get_llm_provider(db)
    llm_model = get_llm_model(llm_provider, db)
    map_provider = get_map_provider(db)

    return {
        "llm": {
            "provider": llm_provider,
            "providerLabel": LLM_PROVIDERS[llm_provider]["label"],
            "model": llm_model,
            "providers": [
                {
                    "id": provider_id,
                    "label": meta["label"],
                    "defaultModel": meta["default_model"],
                    "hasKey": is_present_secret(get_llm_api_key(provider_id, db)),
                    "maskedKey": mask_secret(get_llm_api_key(provider_id, db)),
                }
                for provider_id, meta in LLM_PROVIDERS.items()
            ],
        },
        "map": {
            "provider": map_provider,
            "providerLabel": MAP_PROVIDERS[map_provider]["label"],
            "providers": [
                {
                    "id": provider_id,
                    "label": meta["label"],
                    "hasKey": is_present_secret(get_map_api_key(provider_id, db)),
                    "maskedKey": mask_secret(get_map_api_key(provider_id, db)),
                    "hasSseUrl": bool(get_amap_mcp_sse_url(db)) if provider_id == "amap_mcp_sse" else None,
                }
                for provider_id, meta in MAP_PROVIDERS.items()
            ],
        },
    }
