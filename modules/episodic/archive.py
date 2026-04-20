# 情节记忆的归档逻辑：跨日触发 + 事件摘要生成

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modules.episodic.prompts import EPISODE_SUMMARY_PROMPT
from repository.crud.chats import get_chat, update_chat
from repository.crud.episodes import create_episode
from repository.crud.rounds import (
    get_latest_archived_round,
    get_unarchived_rounds,
    update_round_episode_id,
)
from repository.crud.semantic import list_semantic_memories_by_round_ids
from shared.llm_client import LLMClient
from shared.prompt_utils import render_prompt


ARCHIVE_SYSTEM_PROMPT = "你是一个记忆管理助手。"

# 单个事件的最小回合数阈值：除最新对话回合外，未归档回合数达到此值时才允许触发归档
# 设计原则：一天之内的事情不允许被拆分到不同事件中
MIN_ROUNDS_PER_EPISODE = 5


# 情节记忆归档：判断是否满足归档条件，若满足则将"除最新回合外的所有未归档回合"打包成一个事件
async def archive(
    chat_id: str,
    context: Any,
    db_session: AsyncSession,
    llm_client: LLMClient,
) -> dict[str, Any]:
    chat = await get_chat(db_session, chat_id)
    if chat is None:
        return {"episode_created": False, "new_episode": None}

    unarchived_rounds = await get_unarchived_rounds(db_session, chat_id)

    # 至少需要 2 个未归档回合：1 个作为待归档主体，1 个作为"最新回合"留待下次
    if len(unarchived_rounds) <= 1:
        return {"episode_created": False, "new_episode": None}

    # 待归档范围：除最新回合外的所有未归档回合
    rounds_to_archive = unarchived_rounds[:-1]
    if len(rounds_to_archive) < MIN_ROUNDS_PER_EPISODE:
        return {"episode_created": False, "new_episode": None}

    # 跨日判定：
    # - 启用 semantic：要求最新回合与上一回合的"世界.日期"不同
    # - 未启用 semantic：默认所有回合日期均不同，跨日判定恒为真
    semantic_enabled = "semantic" in chat.enabled_modules
    if semantic_enabled and not await _is_cross_day(
        db_session=db_session,
        chat_id=chat_id,
        latest_round_id=unarchived_rounds[-1].round_id,
        previous_round_id=unarchived_rounds[-2].round_id,
    ):
        return {"episode_created": False, "new_episode": None}

    normalized_context = _normalize_context(context)
    include_first_message = not chat.first_message_archived
    archived_last_round = await get_latest_archived_round(db_session, chat_id)

    # LLM 调用：事件摘要生成
    summary_prompt = render_prompt(
        EPISODE_SUMMARY_PROMPT,
        context=normalized_context,
        include_first_message=include_first_message,
        first_message_summary=chat.first_message,
        archived_last_round=archived_last_round,
        rounds_in_range=rounds_to_archive,
    )
    summary_response = await llm_client.generate_text(
        system_prompt=ARCHIVE_SYSTEM_PROMPT,
        user_prompt=summary_prompt,
    )
    summary_result = _parse_json_object(summary_response)

    title = summary_result.get("title")
    summary = summary_result.get("summary")
    if not isinstance(title, str) or not title.strip():
        return {"episode_created": False, "new_episode": None}
    if not isinstance(summary, str) or not summary.strip():
        return {"episode_created": False, "new_episode": None}

    # 创建事件记录并关联回合
    episode = await create_episode(
        db_session,
        chat_id=chat_id,
        title=title.strip(),
        summary=summary.strip(),
        start_round_id=rounds_to_archive[0].round_id,
        end_round_id=rounds_to_archive[-1].round_id,
    )
    await update_round_episode_id(
        db_session,
        chat_id,
        [round_.round_id for round_ in rounds_to_archive],
        episode.episode_id,
    )

    if include_first_message:
        await update_chat(db_session, chat_id, first_message_archived=True)

    return {
        "episode_created": True,
        "new_episode": {
            "chat_id": episode.chat_id,
            "episode_id": episode.episode_id,
            "title": episode.title,
            "summary": episode.summary,
            "start_round_id": episode.start_round_id,
            "end_round_id": episode.end_round_id,
            "created_at": episode.created_at,
        },
    }


# 判断最新回合与上一回合是否跨日（仅在 semantic 启用时调用）
async def _is_cross_day(
    *,
    db_session: AsyncSession,
    chat_id: str,
    latest_round_id: int,
    previous_round_id: int,
) -> bool:
    snapshots = await list_semantic_memories_by_round_ids(
        db_session, chat_id, [previous_round_id, latest_round_id]
    )
    dates_by_round_id = {
        snapshot.round_id: _extract_world_date(snapshot.content) for snapshot in snapshots
    }
    return dates_by_round_id[previous_round_id] != dates_by_round_id[latest_round_id]


# 从语义记忆快照中提取"世界.日期"字符串（默认字段必定可靠）
def _extract_world_date(snapshot: dict[str, Any]) -> str:
    return snapshot["世界"]["日期"]


# 将 context 统一转为字典格式
def _normalize_context(context: Any) -> dict[str, Any]:
    if context is None:
        return {"extra": ""}
    if hasattr(context, "model_dump"):
        data = context.model_dump()
    elif isinstance(context, dict):
        data = dict(context)
    else:
        data = {"extra": str(context)}
    data.setdefault("extra", "")
    return data


# 从 LLM 返回文本中解析 JSON 对象
def _parse_json_object(text: str) -> dict[str, Any]:
    payload = _extract_json_payload(text)
    if payload is None:
        return {}

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}

    return data if isinstance(data, dict) else {}


# 从 LLM 返回文本中提取 JSON 片段（支持 markdown 代码块包裹）
def _extract_json_payload(text: str) -> str | None:
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced_match:
        text = fenced_match.group(1).strip()

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    return None
