# 管理/调试端点：rounds 和 episodes 的 CRUD 操作

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from repository.crud.episodes import delete_episode, get_all_episodes
from repository.crud.rounds import get_rounds
from repository.database import get_session
from repository.models import Episode, Round
from schemas.episodes import EpisodeDetail

router = APIRouter(prefix="/chats/{chat_id}")


# 获取该角色所有回合，支持按归档状态过滤
@router.get("/rounds")
async def list_rounds_endpoint(
    chat_id: str,
    archived: bool | None = Query(default=None),
    db_session: AsyncSession = Depends(get_session),
) -> list[dict]:
    rounds = await get_rounds(db_session, chat_id, archived=archived)
    return [_serialize_round(round_) for round_ in rounds]


# 获取单个回合详情
@router.get("/rounds/{round_id}")
async def get_round_endpoint(
    chat_id: str,
    round_id: int,
    db_session: AsyncSession = Depends(get_session),
) -> dict:
    round_record = await db_session.get(Round, (chat_id, round_id))
    if round_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found.")
    return _serialize_round(round_record)


# 删除单个回合（若已归档则同时删除所属事件）
@router.delete("/rounds/{round_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_round_endpoint(
    chat_id: str,
    round_id: int,
    db_session: AsyncSession = Depends(get_session),
) -> Response:
    round_record = await db_session.get(Round, (chat_id, round_id))
    if round_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found.")

    if round_record.episode_id is not None:
        await delete_episode(db_session, chat_id, round_record.episode_id)

    await db_session.delete(round_record)
    await db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# 获取该角色所有事件
@router.get("/episodes", response_model=list[EpisodeDetail])
async def list_episodes_endpoint(
    chat_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> list[EpisodeDetail]:
    episodes = await get_all_episodes(db_session, chat_id)
    return [EpisodeDetail.model_validate(episode) for episode in episodes]


# 获取单个事件详情
@router.get("/episodes/{episode_id}", response_model=EpisodeDetail)
async def get_episode_endpoint(
    chat_id: str,
    episode_id: int,
    db_session: AsyncSession = Depends(get_session),
) -> EpisodeDetail:
    episode = await db_session.get(Episode, (chat_id, episode_id))
    if episode is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found.")
    return EpisodeDetail.model_validate(episode)


# 删除单个事件（其下 rounds 的 episode_id 会被重置为 null）
@router.delete("/episodes/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_episode_endpoint(
    chat_id: str,
    episode_id: int,
    db_session: AsyncSession = Depends(get_session),
) -> Response:
    deleted = await delete_episode(db_session, chat_id, episode_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Episode not found.")
    await db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# 将 Round ORM 对象转为字典用于 JSON 响应
def _serialize_round(round_: Round) -> dict:
    return {
        "chat_id": round_.chat_id,
        "round_id": round_.round_id,
        "user_input": round_.user_input,
        "ai_response": round_.ai_response,
        "summary": round_.summary,
        "episode_id": round_.episode_id,
        "created_at": round_.created_at,
    }
