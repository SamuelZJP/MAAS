from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from repository.crud.semantic import get_latest_semantic_memory


async def recall(
    chat_id: str,
    db_session: AsyncSession,
) -> dict[str, Any] | None:
    record = await get_latest_semantic_memory(db_session, chat_id)
    if record is None:
        return None
    return dict(record.content)
