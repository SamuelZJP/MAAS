# 情节记忆的归档逻辑：事件边界检测 + 事件摘要生成

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modules.episodic.prompts import BOUNDARY_DETECT_PROMPT, EPISODE_SUMMARY_PROMPT
from repository.crud.chats import get_chat, update_chat
from repository.crud.episodes import create_episode
from repository.crud.rounds import (
    get_latest_archived_round,
    get_unarchived_rounds,
    update_round_episode_id,
)
from shared.llm_client import LLMClient
from shared.prompt_utils import render_prompt


ARCHIVE_SYSTEM_PROMPT = "你是一个记忆管理助手。"


# 情节记忆归档：检测未归档回合中是否存在事件边界，若有则生成事件
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
    if not unarchived_rounds:
        return {"episode_created": False, "new_episode": None}

    normalized_context = _normalize_context(context)
    include_first_message = not chat.first_message_archived
    archived_last_round = await get_latest_archived_round(db_session, chat_id)
    latest_unarchived_round = unarchived_rounds[-1]

    # LLM 调用 1：事件边界检测
    boundary_prompt = render_prompt(
        BOUNDARY_DETECT_PROMPT,
        context=normalized_context,
        include_first_message=include_first_message,
        first_message_summary=chat.first_message,
        archived_last_round=archived_last_round,
        unarchived_rounds=unarchived_rounds,
        latest_unarchived_round=latest_unarchived_round,
    )
    boundary_response = await llm_client.generate_text(
        system_prompt=ARCHIVE_SYSTEM_PROMPT,
        user_prompt=boundary_prompt,
    )
    boundary_result = _parse_json_object(boundary_response)

    has_boundary = bool(boundary_result.get("has_boundary"))
    if not has_boundary:
        return {"episode_created": False, "new_episode": None}

    rounds_in_range = unarchived_rounds

    # LLM 调用 2：事件摘要生成
    summary_prompt = render_prompt(
        EPISODE_SUMMARY_PROMPT,
        context=normalized_context,
        include_first_message=include_first_message,
        first_message_summary=chat.first_message,
        archived_last_round=archived_last_round,
        rounds_in_range=rounds_in_range,
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
        start_round_id=rounds_in_range[0].round_id,
        end_round_id=rounds_in_range[-1].round_id,
    )
    await update_round_episode_id(
        db_session,
        chat_id,
        [round_.round_id for round_ in rounds_in_range],
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
