# 归档主流程编排：存储回合 → 各模块归档 → 汇总结果

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from modules.episodic.archive import archive as episodic_archive
from repository.crud.chats import get_chat
from repository.crud.rounds import create_round
from repository.models import Round
from schemas.archive import ArchiveResponse
from schemas.episodes import EpisodeDetail
from shared.llm_client import LLMClient


# 归档主流程：先存储本轮对话，再依次调用各模块的归档逻辑
async def run_archive(
    chat_id: str,
    round_data: Any,
    context: Any,
    db_session: AsyncSession,
    llm_client: LLMClient,
    config: Settings,
) -> ArchiveResponse:
    # 幂等性保护：重复 round_id 直接跳过
    existing_round = await db_session.get(Round, (chat_id, _normalize_round_data(round_data)["round_id"]))
    if existing_round is not None:
        return ArchiveResponse(
            round_stored=False,
            episode_created=False,
            new_episode=None,
        )

    stored_round = await _store_round(chat_id, round_data, db_session)

    chat = await get_chat(db_session, chat_id)
    if chat is None:
        return ArchiveResponse(
            round_stored=stored_round,
            episode_created=False,
            new_episode=None,
        )

    episode_created = False
    new_episode = None

    if "episodic" in chat.enabled_modules:
        episodic_result = await episodic_archive(
            chat_id=chat_id,
            context=context,
            db_session=db_session,
            llm_client=llm_client,
        )
        episode_created = bool(episodic_result.get("episode_created"))
        if episode_created and episodic_result.get("new_episode") is not None:
            new_episode = EpisodeDetail(**episodic_result["new_episode"])

    # 未来新增模块时在此处追加归档逻辑（语义记忆应先于工作记忆执行）
    _ = config

    return ArchiveResponse(
        round_stored=stored_round,
        episode_created=episode_created,
        new_episode=new_episode,
    )


# 将本轮对话存入 rounds 表，若已存在则更新内容
async def _store_round(chat_id: str, round_data: Any, db_session: AsyncSession) -> bool:
    data = _normalize_round_data(round_data)
    existing_round = await db_session.get(Round, (chat_id, data["round_id"]))
    if existing_round is None:
        await create_round(
            db_session,
            chat_id=chat_id,
            round_id=data["round_id"],
            user_input=data["user_input"],
            ai_response=data["ai_response"],
            summary=data["summary"],
            episode_id=None,
        )
        return True

    existing_round.user_input = data["user_input"]
    existing_round.ai_response = data["ai_response"]
    existing_round.summary = data["summary"]
    existing_round.episode_id = None
    await db_session.flush()
    return True


# 将 Pydantic 模型或字典统一转为标准字典格式
def _normalize_round_data(round_data: Any) -> dict[str, Any]:
    if hasattr(round_data, "model_dump"):
        data = round_data.model_dump()
    elif isinstance(round_data, dict):
        data = dict(round_data)
    else:
        raise TypeError("round_data must be a mapping or pydantic model.")

    return {
        "round_id": data["round_id"],
        "user_input": data["user_input"],
        "ai_response": data["ai_response"],
        "summary": data["summary"],
    }
