# 记忆召回接口：用户输入发送后、AI 生成前调用

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, get_settings
from core.recall_pipeline import run_recall
from repository.database import get_session
from schemas.recall import RecallRequest, RecallResponse
from shared.llm_client import LLMClient

router = APIRouter()


# 记忆召回入口，转发到 recall_pipeline 编排
@router.post("/recall", response_model=RecallResponse)
async def recall_endpoint(
    payload: RecallRequest,
    db_session: AsyncSession = Depends(get_session),
    config: Settings = Depends(get_settings),
) -> RecallResponse:
    llm_client = LLMClient.from_settings(config)
    response = await run_recall(
        chat_id=payload.chat_id,
        latest_round_id=payload.latest_round_id,
        recall_start_round_id=payload.recall_start_round_id,
        recall_end_round_id=payload.recall_end_round_id,
        context=payload.context,
        db_session=db_session,
        llm_client=llm_client,
        config=config,
    )
    await db_session.commit()
    return response
