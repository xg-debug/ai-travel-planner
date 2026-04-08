from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from typing import Optional
from app.core.config import settings


class UnconfiguredLLM(BaseChatModel):
    def __init__(self, reason: str):
        super().__init__()
        self.reason = reason

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
        max_tokens: Optional[int] = None
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
        
        if provider == "openai":
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_openai_api_key_here" or "test-key" in settings.OPENAI_API_KEY:
                return UnconfiguredLLM("OPENAI_API_KEY 未配置，无法调用 OpenAI 模型")
            from langchain_core.utils import convert_to_secret_str
            return ChatOpenAI(
                api_key=convert_to_secret_str(settings.OPENAI_API_KEY),
                model=model,
                temperature=temperature
            )
        
        elif provider == "anthropic":
            if not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY == "your_anthropic_api_key_here":
                return UnconfiguredLLM("ANTHROPIC_API_KEY 未配置，无法调用 Anthropic 模型")
            from langchain_core.utils import convert_to_secret_str
            return ChatAnthropic(
                api_key=convert_to_secret_str(settings.ANTHROPIC_API_KEY),
                model_name=model,
                temperature=temperature,
                max_tokens_to_sample=max_tokens
            )
        
        elif provider == "google":
            if not settings.GOOGLE_API_KEY or settings.GOOGLE_API_KEY == "your_google_api_key_here":
                return UnconfiguredLLM("GOOGLE_API_KEY 未配置，无法调用 Google 模型")
            return ChatGoogleGenerativeAI(
                api_key=settings.GOOGLE_API_KEY,
                model=model,
                temperature=temperature
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
                temperature=temperature
            )
        
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

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
