from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from typing import Optional
import logging
from app.core.config import settings

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
        provider = provider or settings.DEFAULT_LLM_PROVIDER
        model = model or settings.DEFAULT_LLM_MODEL
        temperature = temperature or settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        request_timeout = settings.LLM_REQUEST_TIMEOUT_SECONDS if request_timeout is None else request_timeout
        max_retries = settings.LLM_MAX_RETRIES if max_retries is None else max_retries
        
        if provider == "openai":
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_api_key_here" or "test-key" in settings.OPENAI_API_KEY:
                return UnconfiguredLLM("OPENAI_API_KEY 未配置，无法调用 OpenAI 模型")
            from langchain_core.utils import convert_to_secret_str
            return ChatOpenAI(
                api_key=convert_to_secret_str(settings.OPENAI_API_KEY),
                model=model,
                temperature=temperature,
                timeout=request_timeout,
                max_retries=max_retries,
            )
        
        elif provider == "anthropic":
            if not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY == "your_anthropic_api_key_here":
                return UnconfiguredLLM("ANTHROPIC_API_KEY 未配置，无法调用 Anthropic 模型")
            from langchain_core.utils import convert_to_secret_str
            return ChatAnthropic(
                api_key=convert_to_secret_str(settings.ANTHROPIC_API_KEY),
                model_name=model,
                temperature=temperature,
                max_tokens_to_sample=max_tokens,
                timeout=request_timeout,
                max_retries=max_retries,
            )
        
        elif provider == "google":
            if not settings.GOOGLE_API_KEY or settings.GOOGLE_API_KEY == "your_google_api_key_here":
                return UnconfiguredLLM("GOOGLE_API_KEY 未配置，无法调用 Google 模型")
            return ChatGoogleGenerativeAI(
                api_key=settings.GOOGLE_API_KEY,
                model=model,
                temperature=temperature,
            )
        
        elif provider == "deepseek":
            # 使用OpenAI兼容接口
            if not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
                return UnconfiguredLLM("DEEPSEEK_API_KEY 未配置，无法调用 DeepSeek 模型")
            from langchain_core.utils import convert_to_secret_str
            return ChatOpenAI(
                api_key=convert_to_secret_str(settings.DEEPSEEK_API_KEY),
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
    if provider == "openai":
        return bool(
            settings.OPENAI_API_KEY
            and settings.OPENAI_API_KEY != "your_openai_api_key_here"
            and "test-key" not in settings.OPENAI_API_KEY
        )
    if provider == "anthropic":
        return bool(settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_API_KEY != "your_anthropic_api_key_here")
    if provider == "google":
        return bool(settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY != "your_google_api_key_here")
    if provider == "deepseek":
        return bool(settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_KEY != "your_deepseek_api_key_here")
    return False


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
    providers = provider_order or [settings.DEFAULT_LLM_PROVIDER, "openai", "anthropic", "google", "deepseek"]
    unique_providers = []
    for provider in providers:
        if provider not in unique_providers:
            unique_providers.append(provider)

    errors: list[str] = []
    for provider in unique_providers:
        if not _provider_has_key(provider):
            continue

        preferred_model = settings.DEFAULT_LLM_MODEL if provider == settings.DEFAULT_LLM_PROVIDER else None
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
    provider=settings.DEFAULT_LLM_PROVIDER,
    model=settings.DEFAULT_LLM_MODEL,
    temperature=0.7,  # 创造性更高
    max_tokens=2000
)

summary_llm = LLMFactory.create_llm(
    provider=settings.DEFAULT_LLM_PROVIDER,
    model=settings.DEFAULT_LLM_MODEL,
    temperature=0.3,  # 更确定性
    max_tokens=1000
)

recommendation_llm = LLMFactory.create_llm(
    provider=settings.DEFAULT_LLM_PROVIDER,
    model=settings.DEFAULT_LLM_MODEL,
    temperature=0.5,
    max_tokens=800
)
