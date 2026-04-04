from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from schemas.episodes import EpisodeSummary


class RecallContext(BaseModel):
    user_input: str
    extra: Any | None = None

    model_config = ConfigDict(extra="allow")


class RecallRequest(BaseModel):
    chat_id: str
    latest_round_id: int
    context: RecallContext


class RecallResponse(BaseModel):
    recalled_episodes: list[EpisodeSummary]
    rollback_performed: bool
    rollback_to_round_id: int | None
