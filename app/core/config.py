"""
MarkFlow API Configuration
"""
from typing import Optional, List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # App
    APP_NAME: str = "MarkFlow API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/v1"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    API_KEY_HEADER: str = "X-API-Key"
    ALLOWED_ORIGINS: List[str] = ["*"]
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 3600  # seconds
    
    # File Upload
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: List[str] = [
        ".pdf", ".docx", ".pptx", ".xlsx", ".xls",
        ".html", ".htm", ".csv", ".json", ".xml",
        ".png", ".jpg", ".jpeg", ".gif", ".bmp",
        ".mp3", ".wav", ".m4a",
        ".epub", ".zip"
    ]
    UPLOAD_DIR: str = "./uploads"
    
    # Redis (for rate limiting & caching)
    REDIS_URL: Optional[str] = None
    
    # OpenAI / LLM
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    
    # Azure Document Intelligence (optional)
    AZURE_DOC_INTEL_ENDPOINT: Optional[str] = None
    
    # Pricing (for OpenRouter)
    PRICE_PER_1K_TOKENS_INPUT: float = 0.001
    PRICE_PER_1K_TOKENS_OUTPUT: float = 0.002
    PRICE_PER_CONVERSION: float = 0.01
    
    # Prometheus
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
