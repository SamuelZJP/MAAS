from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from repository.models import Round


async def create_round(
    session: AsyncSession,
    *,
    chat_id: str,
    round_id: int,
    user_input: str,
    ai_response: str,
    summary: str,
    episode_id: int | None = None,
) -> Round:
    round_record = Round(
        chat_id=chat_id,
        round_id=round_id,
        user_input=user_input,
        ai_response=ai_response,
        summary=summary,
        episode_id=episode_id,
    )
    session.add(round_record)
    await session.flush()
    await session.refresh(round_record)
    return round_record


async def get_rounds(
    session: AsyncSession,
    chat_id: str,
    archived: bool | None = None,
) -> list[Round]:
    stmt = select(Round).where(Round.chat_id == chat_id)
    if archived is True:
        stmt = stmt.where(Round.episode_id.is_not(None))
    elif archived is False:
        stmt = stmt.where(Round.episode_id.is_(None))

    stmt = stmt.order_by(Round.round_id.asc())
    result = await session.scalars(stmt)
    return list(result.all())


async def get_max_round_id(session: AsyncSession, chat_id: str) -> int | None:
    stmt = select(func.max(Round.round_id)).where(Round.chat_id == chat_id)
    return await session.scalar(stmt)


async def get_unarchived_rounds(session: AsyncSession, chat_id: str) -> list[Round]:
    stmt = (
        select(Round)
        .where(Round.chat_id == chat_id, Round.episode_id.is_(None))
        .order_by(Round.round_id.asc())
    )
    result = await session.scalars(stmt)
    return list(result.all())


async def get_recent_rounds(session: AsyncSession, chat_id: str, limit: int) -> list[Round]:
    stmt = (
        select(Round)
        .where(Round.chat_id == chat_id)
        .order_by(Round.round_id.desc())
        .limit(limit)
    )
    result = await session.scalars(stmt)
    return list(reversed(result.all()))


async def update_round_episode_id(
    session: AsyncSession,
    chat_id: str,
    round_ids: Sequence[int],
    episode_id: int | None,
) -> int:
    if not round_ids:
        return 0

    stmt = (
        update(Round)
        .where(Round.chat_id == chat_id, Round.round_id.in_(list(round_ids)))
        .values(episode_id=episode_id)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def delete_rounds_after(session: AsyncSession, chat_id: str, round_id: int) -> int:
    stmt = delete(Round).where(Round.chat_id == chat_id, Round.round_id > round_id)
    result = await session.execute(stmt)
    return result.rowcount or 0
