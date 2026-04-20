# 记忆召回相关的请求体和响应体模型

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.episodes import EpisodeSummary
from schemas.lorebook import LorebookEntryPayload
from schemas.semantic import SemanticMemorySnapshot


# 召回请求体
class RecallRequest(BaseModel):
    chat_id: str
    latest_round_id: int
    max_archived_summary_rounds: int = Field(
        ge=0,
        description="近期摘要中「已归档回合摘要」部分允许包含的最大回合数。",
    )
    active_rounds_count: int = Field(
        ge=0,
        description="当前对话区间所占的回合数（最近 N 个回合，后端不返回这些回合的内容）。",
    )


# 单条近期摘要：对应 rounds 表中某一回合的 summary
class RecalledSummary(BaseModel):
    round_id: int
    summary: str


# 召回响应体：包含召回的事件列表、近期摘要、语义记忆、词条与回滚信息
class RecallResponse(BaseModel):
    recalled_episodes: list[EpisodeSummary]
    recalled_summaries: list[RecalledSummary]
    semantic_memory: SemanticMemorySnapshot | None = None
    lorebook_entries: list[LorebookEntryPayload]
    rollback_performed: bool
    rollback_to_round_id: int | None
