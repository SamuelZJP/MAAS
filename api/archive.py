# 记忆归档接口：AI 回复后调用

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, get_settings
from core.archive_pipeline import run_archive
from repository.database import get_session
from schemas.archive import ArchiveRequest, ArchiveResponse
from shared.llm_client import LLMClient

router = APIRouter()


# 记忆归档入口，转发到 archive_pipeline 编排
@router.post("/archive", response_model=ArchiveResponse)
async def archive_endpoint(
    payload: ArchiveRequest,
    db_session: AsyncSession = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> ArchiveResponse:
    llm_client = LLMClient.from_settings(config)
    response = await run_archive(
        chat_id=payload.chat_id,
        round_data=payload,
        context=payload.context,
        db_session=db_session,
        llm_client=llm_client,
        config=config,
    )
    await db_session.commit()
    return response
