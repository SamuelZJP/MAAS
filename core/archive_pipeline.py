# 归档主流程编排：存储回合 → 各模块归档 → 汇总结果

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings
from modules.episodic.archive import archive as episodic_archive
from modules.semantic.archive import archive as semantic_archive
from repository.crud.chats import get_chat
from repository.crud.rounds import create_round
from repository.models import Round
from schemas.archive import ArchiveResponse
from schemas.episodes import EpisodeDetail
from shared.llm_client import LLMClient
from shared.summarizer import generate_summary


# 归档主流程：先存储本轮对话，再依次调用各模块的归档逻辑
async def run_archive(
    chat_id: str,
    round_data: Any,
    context: Any,
    db_session: AsyncSession,
    llm_client: LLMClient,
    config: Settings,
) -> ArchiveResponse:
    normalized_round_data = _normalize_round_data(round_data)
    resolved_user = _resolve_user(round_data, config)

    # 重复对话回合检查，遇到重复id直接跳过
    existing_round = await db_session.get(Round, (chat_id, normalized_round_data["round_id"]))
    if existing_round is not None:
        return ArchiveResponse(
            round_stored=False,
            episode_created=False,
            new_episode=None,
            semantic_updated=False,
            semantic_memory=None,
        )

    # 获取当前对话角色
    chat = await get_chat(db_session, chat_id)
    if chat is None:
        return ArchiveResponse(
            round_stored=False,
            episode_created=False,
            new_episode=None,
            semantic_updated=False,
            semantic_memory=None,
        )

    episode_created = False
    new_episode = None
    semantic_updated = False
    semantic_memory = None

    # 语义记忆归档: 更新好感度、世界状态等结构性变量
    if "semantic" in chat.enabled_modules:
        semantic_result = await semantic_archive(
            chat_id=chat_id,
            round_id=normalized_round_data["round_id"],
            user_input=normalized_round_data["user_input"],
            ai_response=normalized_round_data["ai_response"],
            context=context,
            user=resolved_user,
            db_session=db_session,
            llm_client=llm_client,
            config=config,
        )
        if not semantic_result.get("archive_succeeded", False):
            return ArchiveResponse(
                round_stored=False,
                episode_created=False,
                new_episode=None,
                semantic_updated=False,
                semantic_memory=None,
            )
        semantic_updated = bool(semantic_result.get("semantic_updated"))
        semantic_memory = semantic_result.get("semantic_memory")

    # 生成对话回合的摘要
    generated_summary = await generate_summary(
        user_input=normalized_round_data["user_input"],
        ai_response=normalized_round_data["ai_response"],
        context=context,
        semantic_memory=semantic_memory,
        user=resolved_user,
        llm_client=llm_client,
    )
    normalized_round_data["summary"] = generated_summary.strip()

    # 存储本轮对话回合
    stored_round = await _store_round(chat_id, normalized_round_data, db_session)

    # 情节记忆归档: 按跨日 + 回合数阈值判定是否触发，若触发则生成事件摘要
    # TODO: 当前情节记忆归档软失败时的逻辑处理暂时不太规范，需要贴合"一处失败，全部失败"的理念
    if "episodic" in chat.enabled_modules:
        episodic_result = await episodic_archive(
            chat_id=chat_id,
            context=context,
            user=resolved_user,
            db_session=db_session,
            llm_client=llm_client,
        )
        episode_created = bool(episodic_result.get("episode_created"))
        if episode_created and episodic_result.get("new_episode") is not None:
            new_episode = EpisodeDetail(**episodic_result["new_episode"])

    return ArchiveResponse(
        round_stored=stored_round,
        episode_created=episode_created,
        new_episode=new_episode,
        semantic_updated=semantic_updated,
        semantic_memory=semantic_memory,
    )


# 将本轮对话存入 rounds 表，若已存在则更新内容
async def _store_round(chat_id: str, round_data: dict[str, Any], db_session: AsyncSession) -> bool:
    data = round_data
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


# 解析本轮的用户角色名：前端提供则使用，否则回退到配置中的默认值
def _resolve_user(round_data: Any, config: Settings) -> str:
    if hasattr(round_data, "model_dump"):
        data = round_data.model_dump()
    elif isinstance(round_data, dict):
        data = round_data
    else:
        data = {}

    user = data.get("user")
    if isinstance(user, str) and user.strip():
        return user.strip()
    return config.default_user


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
        "summary": "",
    }
