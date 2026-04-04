# episodes 表的 CRUD 操作

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from repository.models import Episode, Round


# 创建事件记录，episode_id 自动递增
async def create_episode(
    session: AsyncSession,
    *,
    chat_id: str,
    title: str,
    summary: str,
    start_round_id: int,
    end_round_id: int,
) -> Episode:
    max_episode_id = await session.scalar(
        select(func.max(Episode.episode_id)).where(Episode.chat_id == chat_id)
    )
    next_episode_id = (max_episode_id or 0) + 1

    episode = Episode(
        chat_id=chat_id,
        episode_id=next_episode_id,
        title=title,
        summary=summary,
        start_round_id=start_round_id,
        end_round_id=end_round_id,
    )
    session.add(episode)
    await session.flush()
    await session.refresh(episode)
    return episode


# 获取指定 chat 的所有事件
async def get_all_episodes(session: AsyncSession, chat_id: str) -> list[Episode]:
    stmt = (
        select(Episode)
        .where(Episode.chat_id == chat_id)
        .order_by(Episode.episode_id.asc())
    )
    result = await session.scalars(stmt)
    return list(result.all())


# 查询与指定回合区间有重叠的事件（用于召回范围筛选）
async def get_episodes_overlapping_round_range(
    session: AsyncSession,
    chat_id: str,
    start_round_id: int,
    end_round_id: int,
) -> list[Episode]:
    stmt = (
        select(Episode)
        .where(
            Episode.chat_id == chat_id,
            Episode.start_round_id <= end_round_id,
            Episode.end_round_id >= start_round_id,
        )
        .order_by(Episode.episode_id.asc())
    )
    result = await session.scalars(stmt)
    return list(result.all())


# 根据 episode_id 列表批量查询事件
async def get_episodes_by_ids(
    session: AsyncSession,
    chat_id: str,
    episode_ids: Sequence[int],
) -> list[Episode]:
    if not episode_ids:
        return []

    stmt = (
        select(Episode)
        .where(Episode.chat_id == chat_id, Episode.episode_id.in_(list(episode_ids)))
        .order_by(Episode.episode_id.asc())
    )
    result = await session.scalars(stmt)
    return list(result.all())


# 查询受回滚影响的事件（start 或 end 超过回滚点的事件）
async def get_affected_episodes(session: AsyncSession, chat_id: str, round_id: int) -> list[Episode]:
    stmt = (
        select(Episode)
        .where(
            Episode.chat_id == chat_id,
            (Episode.start_round_id > round_id) | (Episode.end_round_id > round_id),
        )
        .order_by(Episode.episode_id.asc())
    )
    result = await session.scalars(stmt)
    return list(result.all())


# 删除单个事件，并将其下 rounds 的 episode_id 重置为 null
async def delete_episode(session: AsyncSession, chat_id: str, episode_id: int) -> bool:
    await session.execute(
        update(Round)
        .where(Round.chat_id == chat_id, Round.episode_id == episode_id)
        .values(episode_id=None)
    )
    result = await session.execute(
        delete(Episode).where(Episode.chat_id == chat_id, Episode.episode_id == episode_id)
    )
    return result.rowcount > 0


# 删除受回滚影响的所有事件，并重置相关 rounds 的 episode_id
async def delete_episodes_after(session: AsyncSession, chat_id: str, round_id: int) -> int:
    affected_episodes = await get_affected_episodes(session, chat_id, round_id)
    if not affected_episodes:
        return 0

    for episode in affected_episodes:
        if episode.start_round_id <= round_id:
            await session.execute(
                update(Round)
                .where(
                    Round.chat_id == chat_id,
                    Round.episode_id == episode.episode_id,
                    Round.round_id <= round_id,
                )
                .values(episode_id=None)
            )

    affected_ids = [episode.episode_id for episode in affected_episodes]
    await session.execute(
        update(Round)
        .where(Round.chat_id == chat_id, Round.episode_id.in_(affected_ids))
        .values(episode_id=None)
    )
    result = await session.execute(
        delete(Episode).where(Episode.chat_id == chat_id, Episode.episode_id.in_(affected_ids))
    )
    return result.rowcount or 0
