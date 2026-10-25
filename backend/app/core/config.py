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
    
    # 地图服务配置
    MAP_PROVIDER: Optional[str] = os.getenv("MAP_PROVIDER")
    AMAP_API_KEY: Optional[str] = os.getenv("AMAP_API_KEY")
    TENCENT_MAP_API_KEY: Optional[str] = os.getenv("TENCENT_MAP_API_KEY")
    AMAP_MCP_URL: str = os.getenv("AMAP_MCP_URL", "https://mcp.amap.com/mcp")
    AMAP_MCP_SSE_URL: Optional[str] = os.getenv("AMAP_MCP_SSE_URL")
    AMAP_MCP_SSE_MESSAGE_URL: Optional[str] = os.getenv("AMAP_MCP_SSE_MESSAGE_URL")
    AMAP_MCP_API_KEY: Optional[str] = os.getenv("AMAP_MCP_API_KEY")
    AMAP_MCP_HEADERS: Optional[str] = os.getenv("AMAP_MCP_HEADERS")
    AMAP_MCP_TOOL_OVERRIDES: Optional[str] = os.getenv("AMAP_MCP_TOOL_OVERRIDES")
    AMAP_MCP_CONNECT_TIMEOUT: float = float(os.getenv("AMAP_MCP_CONNECT_TIMEOUT", "20"))
    AMAP_MCP_REQUEST_TIMEOUT: float = float(os.getenv("AMAP_MCP_REQUEST_TIMEOUT", "60"))
    AMAP_MCP_MAX_QPS: float = float(os.getenv("AMAP_MCP_MAX_QPS", "2"))
    AMAP_ROAD_GEOMETRY_ENABLED: bool = False
    
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
    DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "deepseek")
    DEFAULT_LLM_MODEL: str = os.getenv("DEFAULT_LLM_MODEL", "deepseek-flash")

    # Centralised provider → default model mapping
    PROVIDER_DEFAULT_MODELS: dict = {
        "openai": "gpt-4o-mini",
        "anthropic": "claude-sonnet-4-6",
        "google": "gemini-2.5-flash",
        "deepseek": "deepseek-flash",
    }
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    LLM_REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "45"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "1"))
    
    # 行程规划配置
    MAX_TRIP_DAYS: int = int(os.getenv("MAX_TRIP_DAYS", "7"))
    MAX_ACTIVITIES_PER_DAY: int = 6
    MIN_ACTIVITY_DURATION: int = 30  # 分钟
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
