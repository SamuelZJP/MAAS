# Chat 相关的请求体和响应体模型

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# 创建角色对话的请求体
class ChatCreate(BaseModel):
    chat_id: str
    first_message: str
    enabled_modules: list[str] = Field(default_factory=list)


# 更新角色对话的请求体（部分更新）
class ChatUpdate(BaseModel):
    enabled_modules: list[str] | None = None


# Chat 完整信息响应体
class ChatResponse(BaseModel):
    chat_id: str
    first_message: str
    first_message_archived: bool
    enabled_modules: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
