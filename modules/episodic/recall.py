# 情节记忆的召回逻辑：筛选与当前对话相关的历史事件

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modules.episodic.prompts import RECALL_PROMPT
from repository.crud.episodes import (
    get_episodes_by_ids,
    get_episodes_overlapping_round_range,
)
from repository.crud.rounds import get_recent_rounds
from schemas.episodes import EpisodeSummary
from shared.llm_client import LLMClient
from shared.prompt_utils import render_prompt


RECALL_SYSTEM_PROMPT = "你是一个记忆管理助手。"


# 情节记忆召回：根据召回范围查询候选事件，再由 LLM 筛选出相关事件
async def recall(
    chat_id: str,
    context: Any,
    recall_start_round_id: int | None,
    recall_end_round_id: int | None,
    db_session: AsyncSession,
    llm_client: LLMClient,
    recent_rounds_count: int,
) -> list[EpisodeSummary]:
    # 未提供完整召回范围时不进行召回
    if recall_start_round_id is None or recall_end_round_id is None:
        return []

    episodes = await get_episodes_overlapping_round_range(
        db_session,
        chat_id,
        recall_start_round_id,
        recall_end_round_id,
    )
    if not episodes:
        return []

    recent_rounds = await get_recent_rounds(db_session, chat_id, recent_rounds_count)
    recent_rounds_text = _build_recent_rounds_text(recent_rounds)

    user_prompt = render_prompt(
        RECALL_PROMPT,
        recent_rounds_text=recent_rounds_text,
        context=_normalize_context(context),
        episodes=episodes,
    )
    response_text = await llm_client.generate_text(
        system_prompt=RECALL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    episode_ids = _parse_episode_ids(response_text)
    if not episode_ids:
        return []

    selected_episodes = await get_episodes_by_ids(db_session, chat_id, episode_ids)
    return [
        EpisodeSummary(
            episode_id=episode.episode_id,
            title=episode.title,
            summary=episode.summary,
        )
        for episode in selected_episodes
    ]


# 将近期回合摘要拼接为文本，供 LLM 上下文使用
def _build_recent_rounds_text(rounds: Sequence[Any]) -> str:
    if not rounds:
        return "无近期回合摘要"
    return "\n".join(f"[回合{round.round_id}] {round.summary}" for round in rounds)


# 将 context 统一转为字典格式
def _normalize_context(context: Any) -> dict[str, Any]:
    if context is None:
        return {"user_input": "", "extra": ""}
    if hasattr(context, "model_dump"):
        return context.model_dump()
    if isinstance(context, dict):
        return {"user_input": context.get("user_input", ""), "extra": context.get("extra", "")}
    return {"user_input": "", "extra": str(context)}


# 从 LLM 返回文本中解析事件 ID 列表（容错处理各种格式）
def _parse_episode_ids(text: str) -> list[int]:
    payload = _extract_json_payload(text, expected="array")
    if payload is None:
        return []

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    episode_ids: list[int] = []
    for item in data:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            episode_ids.append(item)
        elif isinstance(item, str) and item.strip().isdigit():
            episode_ids.append(int(item.strip()))

    return list(dict.fromkeys(episode_ids))


# 从 LLM 返回文本中提取 JSON 片段（支持 markdown 代码块包裹）
def _extract_json_payload(text: str, *, expected: str) -> str | None:
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced_match:
        text = fenced_match.group(1).strip()

    if expected == "array":
        match = re.search(r"\[[\s\S]*\]", text)
    else:
        match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)

    stripped = text.strip()
    if expected == "array" and stripped.startswith("[") and stripped.endswith("]"):
        return stripped
    if expected == "object" and stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    return None
