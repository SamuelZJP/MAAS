# Chat 相关的请求体和响应体模型

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_MODULES = {"episodic", "semantic", "lorebook"}


def _normalize_enabled_modules(value: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for module in value:
        if module not in ALLOWED_MODULES:
            raise ValueError(f"Unsupported module: {module}")
        if module in seen:
            continue
        seen.add(module)
        normalized.append(module)
    return normalized


# 创建角色对话的请求体
class ChatCreate(BaseModel):
    chat_id: str
    first_message: str
    enabled_modules: list[str] = Field(default_factory=list)

    @field_validator("enabled_modules")
    @classmethod
    def validate_enabled_modules(cls, value: list[str]) -> list[str]:
        return _normalize_enabled_modules(value)


# 更新角色对话的请求体（部分更新）
class ChatUpdate(BaseModel):
    enabled_modules: list[str] | None = None

    @field_validator("enabled_modules")
    @classmethod
    def validate_enabled_modules(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        return _normalize_enabled_modules(value)


# Chat 完整信息响应体
class ChatResponse(BaseModel):
    chat_id: str
    first_message: str
    first_message_archived: bool
    enabled_modules: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
