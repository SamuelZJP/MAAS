# chats 表的 CRUD 操作

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from repository.models import Chat


# 创建角色对话记录
async def create_chat(
    session: AsyncSession,
    *,
    chat_id: str,
    first_message: str,
    enabled_modules: Sequence[str] | None = None,
) -> Chat:
    chat = Chat(
        chat_id=chat_id,
        first_message=first_message,
        enabled_modules=list(enabled_modules or []),
    )
    session.add(chat)
    await session.flush()
    await session.refresh(chat)
    return chat


# 根据 chat_id 查询角色对话
async def get_chat(session: AsyncSession, chat_id: str) -> Chat | None:
    return await session.get(Chat, chat_id)


# 部分更新角色对话字段
async def update_chat(session: AsyncSession, chat_id: str, **updates: Any) -> Chat | None:
    chat = await get_chat(session, chat_id)
    if chat is None:
        return None

    for field, value in updates.items():
        if value is None or not hasattr(chat, field):
            continue
        if field == "enabled_modules":
            value = list(value)
        setattr(chat, field, value)

    await session.flush()
    await session.refresh(chat)
    return chat


# 删除角色对话（级联删除 rounds 和 episodes）
async def delete_chat(session: AsyncSession, chat_id: str) -> bool:
    result = await session.execute(delete(Chat).where(Chat.chat_id == chat_id))
    return result.rowcount > 0
