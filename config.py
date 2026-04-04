# 全局配置，通过环境变量或 .env 文件加载（前缀 MAAS_）

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 全局配置项定义，所有环境变量以 MAAS_ 为前缀
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MAAS_",
        extra="ignore",
    )

    recent_rounds_count: int = Field(
        default=10,
        ge=1,
        description="Number of recent round summaries loaded during recall.",
    )
    llm_endpoint: str = Field(
        default="https://api.deepseek.com/chat/completions",
        description="HTTP endpoint for the external LLM API.",
    )
    llm_model: str = Field(
        default="deepseek-chat",
        description="Model identifier used when calling the external LLM API.",
    )
    llm_api_key: str = Field(
        default="sk-d7a8648b5f64479d87efdc891a0660e0",
        description="Optional API key for the external LLM API.",
    )
    llm_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="HTTP timeout used for LLM requests.",
    )
    llm_max_retries: int = Field(
        default=2,
        ge=0,
        description="Maximum retry attempts for transient LLM request failures.",
    )
    llm_mock_mode: bool = Field(
        default=False,
        description="Use built-in mock LLM responses for local smoke testing.",
    )


# 获取全局配置单例（缓存，仅首次调用时实例化）
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
