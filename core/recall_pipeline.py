# 召回主流程编排：同步检查 → 各模块召回 → 汇总结果

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from core.sync import check_and_rollback
from modules.episodic.recall import recall as episodic_recall
from modules.lorebook.recall import recall as lorebook_recall
from modules.semantic.recall import recall as semantic_recall
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

    # 回滚检查: 检测前端与后端的回合 ID 是否一致，若前端有删除则执行回滚
    sync_result = await check_and_rollback(chat_id, latest_round_id, db_session)

    # 获取当前对话角色
    chat = await get_chat(db_session, chat_id)
    if chat is None:
        return RecallResponse(
            recalled_episodes=[],
            semantic_memory=None,
            lorebook_entries=[],
            rollback_performed=sync_result["rollback_performed"],
            rollback_to_round_id=sync_result["rollback_to_round_id"],
        )

    # 语义记忆召回: 返回当前语义记忆快照
    semantic_memory = None
    if "semantic" in chat.enabled_modules:
        semantic_memory = await semantic_recall(chat_id=chat_id, db_session=db_session)

    # 词条记忆召回: 返回当前词条记忆
    lorebook_entries = []
    if "lorebook" in chat.enabled_modules:
        lorebook_entries = await lorebook_recall(
            chat_id=chat_id,
            db_session=db_session,
            semantic_memory=semantic_memory,
        )

    # 情节记忆召回: 根据范围召回与当前对话相关的历史事件
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

    return RecallResponse(
        recalled_episodes=recalled_episodes,
        semantic_memory=semantic_memory,
        lorebook_entries=lorebook_entries,
        rollback_performed=sync_result["rollback_performed"],
        rollback_to_round_id=sync_result["rollback_to_round_id"],
    )
