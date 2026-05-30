from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from typing import Optional
import logging
from app.core.config import settings
from app.services.runtime_config import get_llm_api_key, get_llm_model, get_llm_provider, is_present_secret

logger = logging.getLogger(__name__)

class UnconfiguredLLM(BaseChatModel):
    reason: str

    def __init__(self, reason: str):
        super().__init__(reason=reason)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise RuntimeError(self.reason)

    @property
    def _llm_type(self) -> str:
        return "unconfigured_llm"


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
        """
        创建LLM实例
        
        Args:
            provider: LLM提供商 (openai, anthropic, google, deepseek)
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            BaseChatModel实例
        """
        provider = provider or get_llm_provider()
        model = model or get_llm_model(provider)
        temperature = temperature or settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        request_timeout = settings.LLM_REQUEST_TIMEOUT_SECONDS if request_timeout is None else request_timeout
        max_retries = settings.LLM_MAX_RETRIES if max_retries is None else max_retries
        
        if provider == "openai":
            api_key = get_llm_api_key("openai")
            if not is_present_secret(api_key):
                return UnconfiguredLLM("OPENAI_API_KEY 未配置，无法调用 OpenAI 模型")
            from langchain_core.utils import convert_to_secret_str
            return ChatOpenAI(
                api_key=convert_to_secret_str(api_key),
                model=model,
                temperature=temperature,
                timeout=request_timeout,
                max_retries=max_retries,
            )
        
        elif provider == "anthropic":
            api_key = get_llm_api_key("anthropic")
            if not is_present_secret(api_key):
                return UnconfiguredLLM("ANTHROPIC_API_KEY 未配置，无法调用 Anthropic 模型")
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
            return ChatGoogleGenerativeAI(
                api_key=api_key,
                model=model,
                temperature=temperature,
            )
        
        elif provider == "deepseek":
            # 使用OpenAI兼容接口
            api_key = get_llm_api_key("deepseek")
            if not is_present_secret(api_key):
                return UnconfiguredLLM("DEEPSEEK_API_KEY 未配置，无法调用 DeepSeek 模型")
            from langchain_core.utils import convert_to_secret_str
            return ChatOpenAI(
                api_key=convert_to_secret_str(api_key),
                base_url="https://api.deepseek.com/v1",
                model=model,
                temperature=temperature,
                timeout=request_timeout,
                max_retries=max_retries,
            )
        
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")


PROVIDER_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "google": "gemini-1.5-flash",
    "deepseek": "deepseek-chat",
}


def _provider_has_key(provider: str) -> bool:
    return is_present_secret(get_llm_api_key(provider))


def _resolve_model(provider: str, preferred_model: str | None) -> str:
    if not preferred_model:
        return PROVIDER_DEFAULT_MODELS[provider]
    # 避免配置了不兼容的默认模型（例如 provider=deepseek 但 model=gpt-3.5-turbo）
    if provider != "openai" and preferred_model.startswith("gpt-"):
        return PROVIDER_DEFAULT_MODELS[provider]
    return preferred_model


def invoke_llm_with_fallback(
    prompt: str,
    temperature: float,
    max_tokens: int,
    request_timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
    provider_order: Optional[list[str]] = None,
):
    default_provider = get_llm_provider()
    providers = provider_order or [default_provider, "openai", "anthropic", "google", "deepseek"]
    unique_providers = []
    for provider in providers:
        if provider not in unique_providers:
            unique_providers.append(provider)

    errors: list[str] = []
    for provider in unique_providers:
        if not _provider_has_key(provider):
            continue

        preferred_model = get_llm_model(provider) if provider == default_provider else None
        model = _resolve_model(provider, preferred_model)
        try:
            llm = LLMFactory.create_llm(
                provider=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                request_timeout=request_timeout,
                max_retries=max_retries,
            )
            logger.info("Invoking LLM provider=%s model=%s", provider, model)
            return llm.invoke(prompt)
        except Exception as exc:
            err = f"{provider}: {exc}"
            errors.append(err)
            logger.warning("LLM provider failed: %s", err)
            continue

    if not errors:
        raise RuntimeError("未检测到可用的 LLM API Key，请先配置至少一个可用模型")
    raise RuntimeError(f"所有模型调用失败：{' | '.join(errors)}")

# 默认LLM实例
default_llm = LLMFactory.create_llm()

# 专用LLM实例（针对不同任务可以配置不同参数）
planner_llm = LLMFactory.create_llm(
    provider=get_llm_provider(),
    model=get_llm_model(),
    temperature=0.7,  # 创造性更高
    max_tokens=2000
)

summary_llm = LLMFactory.create_llm(
    provider=get_llm_provider(),
    model=get_llm_model(),
    temperature=0.3,  # 更确定性
    max_tokens=1000
)

recommendation_llm = LLMFactory.create_llm(
    provider=get_llm_provider(),
    model=get_llm_model(),
    temperature=0.5,
    max_tokens=800
)
