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

    llm_endpoint: str = Field(
        default="https://api.deepseek.com/chat/completions",
        description="HTTP endpoint for the external LLM API.",
    )
    llm_model: str = Field(
        default="deepseek-v4-pro",
        description="Model identifier used when calling the external LLM API.",
    )
    llm_api_key: str = Field(
        default="sk-example",
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
    default_user: str = Field(
        default="周嘉鹏",
        description="Fallback persona name injected as {{user}} when the request omits it.",
    )
    semantic_recent_summary_rounds: int = Field(
        default=5,
        ge=0,
        description=(
            "Number of preceding rounds whose summaries are fed to the semantic "
            "archive LLM as recent-plot context. 0 disables the feature (legacy behavior)."
        ),
    )


# 获取全局配置单例（缓存，仅首次调用时实例化）
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
