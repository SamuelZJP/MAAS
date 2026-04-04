from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EpisodeBase(BaseModel):
    title: str
    summary: str


class EpisodeSummary(EpisodeBase):
    episode_id: int

    model_config = ConfigDict(from_attributes=True)


class EpisodeDetail(EpisodeSummary):
    chat_id: str
    start_round_id: int
    end_round_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
