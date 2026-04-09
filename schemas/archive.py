# 记忆归档相关的请求体和响应体模型

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from schemas.episodes import EpisodeDetail
from schemas.semantic import SemanticMemorySnapshot


# 归档请求中的上下文信息（前端额外上下文）
class ArchiveContext(BaseModel):
    extra: Any | None = None

    model_config = ConfigDict(extra="allow")


# 归档请求体：包含本轮对话的完整数据
class ArchiveRequest(BaseModel):
    chat_id: str
    round_id: int
    user_input: str
    ai_response: str
    # 兼容保留字段：后端已忽略前端传入的 summary，统一自行生成
    summary: str
    context: ArchiveContext


# 归档响应体：回合是否存储成功、是否产生了新事件
class ArchiveResponse(BaseModel):
    round_stored: bool
    episode_created: bool
    new_episode: EpisodeDetail | None
    semantic_updated: bool = False
    semantic_memory: SemanticMemorySnapshot | None = None
