# 回滚/同步逻辑：检测前端楼层删除并回滚后端数据

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from repository.crud.chats import update_chat
from repository.crud.episodes import delete_episodes_after, get_affected_episodes
from repository.crud.rounds import delete_rounds_after, get_max_round_id


# 检查前端与后端的回合 ID 是否一致，若前端有删除则执行回滚
async def check_and_rollback(
    chat_id: str,
    latest_round_id: int,
    db_session: AsyncSession,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        max_round_id = await get_max_round_id(db_session, chat_id)
        if max_round_id is None or latest_round_id >= max_round_id:
            return {
                "rollback_performed": False,
                "rollback_to_round_id": None,
            }

        affected_episodes = await get_affected_episodes(db_session, chat_id, latest_round_id)
        deleted_first_episode = any(episode.episode_id == 1 for episode in affected_episodes)

        if affected_episodes:
            await delete_episodes_after(db_session, chat_id, latest_round_id)

        await delete_rounds_after(db_session, chat_id, latest_round_id)

        if deleted_first_episode:
            await update_chat(db_session, chat_id, first_message_archived=False)

        return {
            "rollback_performed": True,
            "rollback_to_round_id": latest_round_id,
        }

    if db_session.in_transaction():
        return await _run()

    async with db_session.begin():
        return await _run()
