# Chat 管理接口：创建、查询、更新、删除角色对话

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from repository.crud.chats import create_chat, delete_chat, get_chat, update_chat
from repository.database import get_session
from schemas.chats import ChatCreate, ChatResponse, ChatUpdate

router = APIRouter(prefix="/chats")


# 初始化角色对话
@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_endpoint(
    payload: ChatCreate,
    db_session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    chat = await create_chat(
        db_session,
        chat_id=payload.chat_id,
        first_message=payload.first_message,
        enabled_modules=payload.enabled_modules,
    )
    await db_session.commit()
    return ChatResponse.model_validate(chat)


# 获取角色对话配置
@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat_endpoint(
    chat_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    chat = await get_chat(db_session, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found.")
    return ChatResponse.model_validate(chat)


# 更新角色对话配置（部分更新）
@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat_endpoint(
    chat_id: str,
    payload: ChatUpdate,
    db_session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    chat = await update_chat(db_session, chat_id, **payload.model_dump(exclude_unset=True))
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found.")
    await db_session.commit()
    return ChatResponse.model_validate(chat)


# 删除角色对话及其所有关联数据（级联删除 rounds 和 episodes）
@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_endpoint(
    chat_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> Response:
    deleted = await delete_chat(db_session, chat_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found.")
    await db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
