# Episode（事件）相关的响应体模型

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# 事件基础字段
class EpisodeBase(BaseModel):
    title: str
    summary: str


# 事件摘要（用于召回结果返回）
class EpisodeSummary(EpisodeBase):
    episode_id: int

    model_config = ConfigDict(from_attributes=True)


# 事件完整详情（用于管理接口和归档结果返回）
class EpisodeDetail(EpisodeSummary):
    chat_id: str
    start_round_id: int
    end_round_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
