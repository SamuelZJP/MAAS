# 召回主流程编排：同步检查 → 各模块召回 → 汇总结果

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.sync import check_and_rollback
from modules.episodic.recall import recall as episodic_recall
from modules.lorebook.recall import recall as lorebook_recall
from modules.semantic.recall import recall as semantic_recall
from schemas.recall import RecallResponse


# 召回主流程：先执行回滚检查，再依次调用各模块的召回逻辑
async def run_recall(
    chat_id: str,
    latest_round_id: int,
    max_archived_summary_rounds: int,
    active_rounds_count: int,
    db_session: AsyncSession,
) -> RecallResponse:

    # 回滚检查: 检测前端与后端的回合 ID 是否一致，若前端有删除则执行回滚
    sync_result = await check_and_rollback(chat_id, latest_round_id, db_session)

    # 语义记忆召回: 返回当前语义记忆快照
    semantic_memory = await semantic_recall(chat_id=chat_id, db_session=db_session)

    # 词条记忆召回: 返回当前词条记忆
    lorebook_entries = await lorebook_recall(
        chat_id=chat_id,
        db_session=db_session,
        semantic_memory=semantic_memory,
    )

    # 情节记忆与近期摘要召回: 按"事件 + 回合摘要"两段返回
    recalled_episodes, recalled_summaries = await episodic_recall(
        chat_id=chat_id,
        max_archived_summary_rounds=max_archived_summary_rounds,
        active_rounds_count=active_rounds_count,
        db_session=db_session,
    )

    return RecallResponse(
        recalled_episodes=recalled_episodes,
        recalled_summaries=recalled_summaries,
        semantic_memory=semantic_memory,
        lorebook_entries=lorebook_entries,
        rollback_performed=sync_result["rollback_performed"],
        rollback_to_round_id=sync_result["rollback_to_round_id"],
    )
