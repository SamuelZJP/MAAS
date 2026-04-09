# 记忆召回相关的请求体和响应体模型

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from schemas.episodes import EpisodeSummary
from schemas.semantic import SemanticMemorySnapshot


# 召回请求中的上下文信息（用户输入 + 前端额外上下文）
class RecallContext(BaseModel):
    user_input: str
    extra: Any | None = None

    model_config = ConfigDict(extra="allow")


# 召回请求体
class RecallRequest(BaseModel):
    chat_id: str
    latest_round_id: int
    recall_start_round_id: int | None = None
    recall_end_round_id: int | None = None
    context: RecallContext


# 召回响应体：包含召回的事件列表和回滚信息
class RecallResponse(BaseModel):
    recalled_episodes: list[EpisodeSummary]
    semantic_memory: SemanticMemorySnapshot | None = None
    rollback_performed: bool
    rollback_to_round_id: int | None
