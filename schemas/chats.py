from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatCreate(BaseModel):
    chat_id: str
    first_message: str
    enabled_modules: list[str] = Field(default_factory=list)


class ChatUpdate(BaseModel):
    enabled_modules: list[str] | None = None


class ChatResponse(BaseModel):
    chat_id: str
    first_message: str
    first_message_archived: bool
    enabled_modules: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
