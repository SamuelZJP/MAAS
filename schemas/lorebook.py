from __future__ import annotations

from pydantic import BaseModel


class LorebookEntryPayload(BaseModel):
    entry_id: int
    content: str
    position: str
    order: int
    depth: int | None
