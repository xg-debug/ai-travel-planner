from typing import Any, Generator, Optional
import logging
from app.core.config import settings
from app.services.runtime_config import get_llm_api_key, get_llm_model, get_llm_provider, is_present_secret

logger = logging.getLogger(__name__)

try:
    from langchain_core.language_models import BaseChatModel
except Exception:  # pragma: no cover - dependency is installed in the backend runtime.
    BaseChatModel = Any  # type: ignore[misc, assignment]


class UnconfiguredLLM:
    def __init__(self, reason: str):
        self.reason = reason

    def invoke(self, *_args, **_kwargs):
        raise RuntimeError(self.reason)

    def stream(self, *_args, **_kwargs):
        raise RuntimeError(self.reason)


class LLMFactory:
    """LLM工厂类，支持多个提供商"""

    @staticmethod
    def create_llm(
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        request_timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> BaseChatModel:
        provider = provider or get_llm_provider()
        model = model or get_llm_model(provider)
        temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        request_timeout = settings.LLM_REQUEST_TIMEOUT_SECONDS if request_timeout is None else request_timeout
        max_retries = settings.LLM_MAX_RETRIES if max_retries is None else max_retries

        if provider == "openai":
            api_key = get_llm_api_key("openai")
            if not is_present_secret(api_key):
                return UnconfiguredLLM("OPENAI_API_KEY 未配置，无法调用 OpenAI 模型")
            from langchain_openai import ChatOpenAI
            from langchain_core.utils import convert_to_secret_str
            return ChatOpenAI(
                api_key=convert_to_secret_str(api_key),
                model=model,
                temperature=temperature,
                timeout=request_timeout,
                max_retries=max_retries,
                max_completion_tokens=max_tokens,
            )

        elif provider == "anthropic":
            api_key = get_llm_api_key("anthropic")
            if not is_present_secret(api_key):
                return UnconfiguredLLM("ANTHROPIC_API_KEY 未配置，无法调用 Anthropic 模型")
            from langchain_anthropic import ChatAnthropic
            from langchain_core.utils import convert_to_secret_str
            return ChatAnthropic(
                api_key=convert_to_secret_str(api_key),
                model_name=model,
                temperature=temperature,
                max_tokens_to_sample=max_tokens,
                timeout=request_timeout,
                max_retries=max_retries,
            )

        elif provider == "google":
            api_key = get_llm_api_key("google")
            if not is_present_secret(api_key):
                return UnconfiguredLLM("GOOGLE_API_KEY 未配置，无法调用 Google 模型")
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                api_key=api_key,
                model=model,
                temperature=temperature,
            )

        elif provider == "deepseek":
            api_key = get_llm_api_key("deepseek")
            if not is_present_secret(api_key):
                return UnconfiguredLLM("DEEPSEEK_API_KEY 未配置，无法调用 DeepSeek 模型")
            from langchain_openai import ChatOpenAI
            from langchain_core.utils import convert_to_secret_str
            return ChatOpenAI(
                api_key=convert_to_secret_str(api_key),
                base_url="https://api.deepseek.com/v1",
                model=model,
                temperature=temperature,
                timeout=request_timeout,
                max_retries=max_retries,
                max_tokens=max_tokens,
            )

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")


def _provider_default_model(provider: str) -> str:
    return settings.PROVIDER_DEFAULT_MODELS.get(provider, "gpt-4o-mini")


def _provider_has_key(provider: str) -> bool:
    return is_present_secret(get_llm_api_key(provider))


def _resolve_model(provider: str, preferred_model: str | None) -> str:
    if not preferred_model:
        return _provider_default_model(provider)
    if provider != "openai" and preferred_model.startswith("gpt-"):
        return _provider_default_model(provider)
    return preferred_model


def _try_create_llm(provider: str, temperature: float, max_tokens: int,
                    request_timeout: Optional[int], max_retries: Optional[int],
                    default_provider: str) -> BaseChatModel | None:
    if not _provider_has_key(provider):
        return None
    preferred_model = get_llm_model(provider)
    model = _resolve_model(provider, preferred_model)
    try:
        return LLMFactory.create_llm(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
            max_retries=max_retries,
        )
    except Exception as exc:
        logger.warning("LLM create failed provider=%s error=%s", provider, exc)
        return None


def invoke_llm_with_fallback(
    prompt: str,
    temperature: float,
    max_tokens: int,
    request_timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
    provider_order: Optional[list[str]] = None,
):
    default_provider = get_llm_provider()
    providers = provider_order or [default_provider]
    unique_providers = []
    for provider in providers:
        if provider not in unique_providers:
            unique_providers.append(provider)

    errors: list[str] = []
    for provider in unique_providers:
        llm = _try_create_llm(provider, temperature, max_tokens, request_timeout, max_retries, default_provider)
        if not llm:
            continue
        try:
            logger.info("Invoking LLM provider=%s", provider)
            response = llm.invoke(prompt)
            if isinstance(getattr(response, "content", None), list):
                response = response.model_copy(update={"content": _message_text(response)})
            return response
        except Exception as exc:
            err = f"{provider}: {exc}"
            errors.append(err)
            logger.warning("LLM provider failed: %s", err)
            continue

    if not errors:
        raise RuntimeError("未检测到可用的 LLM API Key，请先配置至少一个可用模型")
    raise RuntimeError(f"所有模型调用失败：{' | '.join(errors)}")


def stream_llm_with_fallback(
    prompt: str,
    temperature: float,
    max_tokens: int,
    request_timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
    provider_order: Optional[list[str]] = None,
) -> Generator[str, None, None]:
    """Stream LLM response token by token, falling back across providers."""
    default_provider = get_llm_provider()
    providers = provider_order or [default_provider]
    unique_providers: list[str] = []
    for provider in providers:
        if provider not in unique_providers:
            unique_providers.append(provider)

    errors: list[str] = []
    for provider in unique_providers:
        llm = _try_create_llm(provider, temperature, max_tokens, request_timeout, max_retries, default_provider)
        if not llm:
            continue
        try:
            logger.info("Streaming LLM provider=%s", provider)
            for chunk in llm.stream(prompt):
                content = _message_text(chunk)
                if content:
                    yield content
            return
        except Exception as exc:
            err = f"{provider}: {exc}"
            errors.append(err)
            logger.warning("LLM stream provider failed: %s", err)
            continue

    if not errors:
        raise RuntimeError("未检测到可用的 LLM API Key，请先配置至少一个可用模型")
    raise RuntimeError(f"所有模型调用失败：{' | '.join(errors)}")


def _message_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, list):
        # Responses uses content blocks. Only visible text belongs in itinerary
        # JSON or the UI stream; reasoning/tool metadata is not answer text.
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") in {None, "text", "output_text"}:
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content or "")


default_llm = LLMFactory.create_llm()
planner_llm = LLMFactory.create_llm(
    temperature=0.7,
    max_tokens=2000,
)
summary_llm = LLMFactory.create_llm(
    temperature=0.3,
    max_tokens=1000,
)
recommendation_llm = LLMFactory.create_llm(
    temperature=0.5,
    max_tokens=800,
)
