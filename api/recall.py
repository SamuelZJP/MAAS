# 记忆召回接口：用户输入发送后、AI 生成前调用

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.recall_pipeline import run_recall
from repository.database import get_session
from schemas.recall import RecallRequest, RecallResponse

router = APIRouter()


# 记忆召回入口，转发到 recall_pipeline 编排
@router.post("/recall", response_model=RecallResponse)
async def recall_endpoint(
    payload: RecallRequest,
    db_session: AsyncSession = Depends(get_session),
) -> RecallResponse:
    response = await run_recall(
        chat_id=payload.chat_id,
        latest_round_id=payload.latest_round_id,
        max_archived_summary_rounds=payload.max_archived_summary_rounds,
        active_rounds_count=payload.active_rounds_count,
        db_session=db_session,
    )
    await db_session.commit()
    return response
