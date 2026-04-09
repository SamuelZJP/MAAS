from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


SemanticMemorySnapshot = dict[str, Any]


class SemanticMemoryDetail(BaseModel):
    chat_id: str
    round_id: int
    content: SemanticMemorySnapshot
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SemanticMemoryUpdateRequest(BaseModel):
    content: SemanticMemorySnapshot
