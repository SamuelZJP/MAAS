# rounds 表的 CRUD 操作

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from repository.models import Round


# 创建对话回合记录
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


# 查询指定 chat 的回合列表，可按归档状态过滤
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


# 获取指定 chat 的最大 round_id（用于回滚检查）
async def get_max_round_id(session: AsyncSession, chat_id: str) -> int | None:
    stmt = select(func.max(Round.round_id)).where(Round.chat_id == chat_id)
    return await session.scalar(stmt)


# 获取所有未归档的回合（episode_id 为 null），按 round_id 升序
async def get_unarchived_rounds(session: AsyncSession, chat_id: str) -> list[Round]:
    stmt = (
        select(Round)
        .where(Round.chat_id == chat_id, Round.episode_id.is_(None))
        .order_by(Round.round_id.asc())
    )
    result = await session.scalars(stmt)
    return list(result.all())


# 获取最后一个已归档回合（按 round_id 最大）
async def get_latest_archived_round(session: AsyncSession, chat_id: str) -> Round | None:
    stmt = (
        select(Round)
        .where(Round.chat_id == chat_id, Round.episode_id.is_not(None))
        .order_by(Round.round_id.desc())
        .limit(1)
    )
    return await session.scalar(stmt)


# 获取最近 N 轮回合（按 round_id 正序返回，用于组装 LLM 上下文）
async def get_recent_rounds(session: AsyncSession, chat_id: str, limit: int) -> list[Round]:
    stmt = (
        select(Round)
        .where(Round.chat_id == chat_id)
        .order_by(Round.round_id.desc())
        .limit(limit)
    )
    result = await session.scalars(stmt)
    return list(reversed(result.all()))


# 批量更新指定回合的 episode_id（归档时关联事件，或回滚时重置为 null）
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


# 删除指定 round_id 之后的所有回合（回滚时使用）
async def delete_rounds_after(session: AsyncSession, chat_id: str, round_id: int) -> int:
    stmt = delete(Round).where(Round.chat_id == chat_id, Round.round_id > round_id)
    result = await session.execute(stmt)
    return result.rowcount or 0
