from pydantic_settings import BaseSettings
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "AI Travel Planner"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # 服务器配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    
    # 数据库配置
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
    )
    
    # Redis配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # API密钥配置
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    DEEPSEEK_API_KEY: Optional[str] = os.getenv("DEEPSEEK_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    UNSPLASH_ACCESS_KEY: Optional[str] = os.getenv("UNSPLASH_ACCESS_KEY")
    UNSPLASH_SECRET_KEY: Optional[str] = os.getenv("UNSPLASH_SECRET_KEY")
    
    # 地图服务配置
    AMAP_API_KEY: Optional[str] = os.getenv("AMAP_API_KEY")
    TENCENT_MAP_API_KEY: Optional[str] = os.getenv("TENCENT_MAP_API_KEY")
    BAIDU_MAP_API_KEY: Optional[str] = os.getenv("BAIDU_MAP_API_KEY")
    
    # 天气服务配置
    WEATHER_API_KEY: Optional[str] = os.getenv("WEATHER_API_KEY")
    
    # 旅游数据API
    TRIP_ADVISOR_API_KEY: Optional[str] = os.getenv("TRIP_ADVISOR_API_KEY")
    YELP_API_KEY: Optional[str] = os.getenv("YELP_API_KEY")

    # 酒店 MCP 配置
    HOTEL_PROVIDER: str = os.getenv("HOTEL_PROVIDER", "auto")
    ROLLINGGO_API_KEY: Optional[str] = os.getenv("ROLLINGGO_API_KEY")
    AIGOHOTEL_API_KEY: Optional[str] = os.getenv("AIGOHOTEL_API_KEY")
    AGENTICHOTEL_MCP_COMMAND: str = os.getenv("AGENTICHOTEL_MCP_COMMAND", "uvx")
    AGENTICHOTEL_MCP_ARGS: str = os.getenv("AGENTICHOTEL_MCP_ARGS", "--from rollinggo-mcp rollinggo-mcp")
    AGENTICHOTEL_MCP_CWD: Optional[str] = os.getenv("AGENTICHOTEL_MCP_CWD")
    AGENTICHOTEL_MCP_STARTUP_TIMEOUT: float = float(os.getenv("AGENTICHOTEL_MCP_STARTUP_TIMEOUT", "20"))
    AGENTICHOTEL_MCP_REQUEST_TIMEOUT: float = float(os.getenv("AGENTICHOTEL_MCP_REQUEST_TIMEOUT", "60"))

    # 安全配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
    ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER_ME: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES_REMEMBER_ME", "43200")
    )
    
    # 缓存配置
    CACHE_TTL: int = 3600  # 1小时
    
    # 限流配置
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # 文件上传配置
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR: str = "./uploads"
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: Optional[str] = os.getenv("LOG_FILE")
    
    # 模型配置
    DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "openai")
    DEFAULT_LLM_MODEL: str = os.getenv("DEFAULT_LLM_MODEL", "gpt-3.5-turbo")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    LLM_REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "45"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "1"))
    ENABLE_LLM_RECOMMENDATION: bool = os.getenv("ENABLE_LLM_RECOMMENDATION", "false").lower() == "true"
    
    # 行程规划配置
    MAX_TRIP_DAYS: int = int(os.getenv("MAX_TRIP_DAYS", "7"))
    MAX_ACTIVITIES_PER_DAY: int = 6
    MIN_ACTIVITY_DURATION: int = 30  # 分钟
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
