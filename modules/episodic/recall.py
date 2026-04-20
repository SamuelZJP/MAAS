# 情节记忆的召回逻辑：根据回合分区将事件归入"情节记忆"或"近期摘要"

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from repository.crud.episodes import get_all_episodes
from repository.crud.rounds import get_max_round_id, get_rounds_in_range
from schemas.episodes import EpisodeSummary
from schemas.recall import RecalledSummary


# 情节记忆与近期摘要的联合召回。
#
# 输入：
# - max_archived_summary_rounds：近期摘要中"已归档回合摘要"部分允许包含的最大回合数。
# - active_rounds_count：当前对话区间所占的回合数（最近 N 个回合，不返回）。
#
# 算法（以"回滚后 DB 中最大 round_id"为锚点）：
# 1. 非当前对话回合区间：round_id ∈ [1, max_round_id - active_rounds_count]，简称 [1, threshold]。
# 2. 该区间内 episode_id 为空的"未归档回合"全部进入近期摘要。
# 3. 已归档事件按 episode_id 升序排列后，从最新事件开始倒序累加：
#    - 始终保证至少 1 个事件被纳入近期摘要（即使该事件回合数已经超过 limit）。
#    - 后续事件仅当"累计回合数 + 当前事件回合数 ≤ limit"时才纳入，否则停止累加。
# 4. 被纳入近期摘要的事件覆盖的回合摘要进入近期摘要；其余更早的事件作为情节记忆返回。
async def recall(
    chat_id: str,
    max_archived_summary_rounds: int,
    active_rounds_count: int,
    db_session: AsyncSession,
) -> tuple[list[EpisodeSummary], list[RecalledSummary]]:
    max_round_id = await get_max_round_id(db_session, chat_id)
    if max_round_id is None:
        return [], []

    # 非当前对话回合区间的上界（含）
    threshold = max_round_id - active_rounds_count
    if threshold < 1:
        return [], []

    all_episodes = await get_all_episodes(db_session, chat_id)

    # 选出"进入近期摘要"的事件集合（从最新事件向前累加，至少包含一个事件）
    summary_episode_ids = _select_summary_episode_ids(
        all_episodes, max_archived_summary_rounds
    )

    # 剩余的更早事件作为情节记忆返回（按 episode_id 升序）
    recalled_episodes_orm = [
        episode for episode in all_episodes if episode.episode_id not in summary_episode_ids
    ]

    # 非当前对话区间内的所有回合：未归档全部保留，已归档仅保留进入近期摘要的事件对应的回合
    candidate_rounds = await get_rounds_in_range(db_session, chat_id, 1, threshold)
    recalled_summaries = [
        RecalledSummary(round_id=round_.round_id, summary=round_.summary)
        for round_ in candidate_rounds
        if round_.episode_id is None or round_.episode_id in summary_episode_ids
    ]

    return _to_episode_summaries(recalled_episodes_orm), recalled_summaries


# 选出进入近期摘要的事件 ID 集合（按算法：从最新事件向前累加，至少 1 个）
def _select_summary_episode_ids(
    all_episodes: Sequence[Any], max_archived_summary_rounds: int
) -> set[int]:
    summary_ids: set[int] = set()
    total_rounds = 0
    for episode in reversed(all_episodes):
        episode_round_count = episode.end_round_id - episode.start_round_id + 1
        if not summary_ids:
            # 硬约束：至少包含一个事件，即使该事件本身超过上限也要纳入
            summary_ids.add(episode.episode_id)
            total_rounds += episode_round_count
            continue
        if total_rounds + episode_round_count > max_archived_summary_rounds:
            break
        summary_ids.add(episode.episode_id)
        total_rounds += episode_round_count
    return summary_ids


# 将事件 ORM 记录转换为响应模型
def _to_episode_summaries(episodes: Sequence[Any]) -> list[EpisodeSummary]:
    return [
        EpisodeSummary(
            episode_id=episode.episode_id,
            title=episode.title,
            summary=episode.summary,
            start_round_id=episode.start_round_id,
            end_round_id=episode.end_round_id,
        )
        for episode in episodes
    ]
