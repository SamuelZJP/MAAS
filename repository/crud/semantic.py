from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from repository.models import SemanticMemory


async def create_semantic_memory(
    session: AsyncSession,
    *,
    chat_id: str,
    round_id: int,
    content: Mapping[str, Any],
) -> SemanticMemory:
    record = SemanticMemory(
        chat_id=chat_id,
        round_id=round_id,
        content=dict(content),
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)
    return record


async def get_semantic_memory(
    session: AsyncSession,
    chat_id: str,
    round_id: int,
) -> SemanticMemory | None:
    return await session.get(SemanticMemory, (chat_id, round_id))


async def get_latest_semantic_memory(
    session: AsyncSession,
    chat_id: str,
) -> SemanticMemory | None:
    stmt = (
        select(SemanticMemory)
        .where(SemanticMemory.chat_id == chat_id)
        .order_by(SemanticMemory.round_id.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def list_semantic_memories(
    session: AsyncSession,
    chat_id: str,
) -> list[SemanticMemory]:
    stmt = (
        select(SemanticMemory)
        .where(SemanticMemory.chat_id == chat_id)
        .order_by(SemanticMemory.round_id.asc())
    )
    result = await session.scalars(stmt)
    return list(result.all())


async def upsert_semantic_memory(
    session: AsyncSession,
    *,
    chat_id: str,
    round_id: int,
    content: Mapping[str, Any],
) -> SemanticMemory:
    record = await get_semantic_memory(session, chat_id, round_id)
    if record is None:
        return await create_semantic_memory(
            session,
            chat_id=chat_id,
            round_id=round_id,
            content=content,
        )

    record.content = dict(content)
    await session.flush()
    await session.refresh(record)
    return record


async def delete_semantic_memories_after(
    session: AsyncSession,
    chat_id: str,
    round_id: int,
) -> int:
    stmt = delete(SemanticMemory).where(
        SemanticMemory.chat_id == chat_id,
        SemanticMemory.round_id > round_id,
    )
    result = await session.execute(stmt)
    return result.rowcount or 0
