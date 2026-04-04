from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from schemas.episodes import EpisodeDetail


class ArchiveContext(BaseModel):
    extra: Any | None = None

    model_config = ConfigDict(extra="allow")


class ArchiveRequest(BaseModel):
    chat_id: str
    round_id: int
    user_input: str
    ai_response: str
    summary: str
    context: ArchiveContext


class ArchiveResponse(BaseModel):
    round_stored: bool
    episode_created: bool
    new_episode: EpisodeDetail | None
