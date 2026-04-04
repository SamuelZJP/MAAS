# 召回主流程编排：同步检查 → 各模块召回 → 汇总结果

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from core.sync import check_and_rollback
from modules.episodic.recall import recall as episodic_recall
from repository.crud.chats import get_chat
from schemas.recall import RecallResponse
from shared.llm_client import LLMClient


# 召回主流程：先执行回滚检查，再依次调用各模块的召回逻辑
async def run_recall(
    chat_id: str,
    latest_round_id: int,
    recall_start_round_id: int | None,
    recall_end_round_id: int | None,
    context: Any,
    db_session: AsyncSession,
    llm_client: LLMClient,
    config: Settings,
) -> RecallResponse:
    sync_result = await check_and_rollback(chat_id, latest_round_id, db_session)

    chat = await get_chat(db_session, chat_id)
    if chat is None:
        return RecallResponse(
            recalled_episodes=[],
            rollback_performed=sync_result["rollback_performed"],
            rollback_to_round_id=sync_result["rollback_to_round_id"],
        )

    recalled_episodes = []
    if "episodic" in chat.enabled_modules:
        recalled_episodes = await episodic_recall(
            chat_id=chat_id,
            context=context,
            recall_start_round_id=recall_start_round_id,
            recall_end_round_id=recall_end_round_id,
            db_session=db_session,
            llm_client=llm_client,
            recent_rounds_count=config.recent_rounds_count,
        )

    # 未来新增模块时在此处追加召回结果
    return RecallResponse(
        recalled_episodes=recalled_episodes,
        rollback_performed=sync_result["rollback_performed"],
        rollback_to_round_id=sync_result["rollback_to_round_id"],
    )
