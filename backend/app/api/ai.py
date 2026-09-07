from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.ai.factory import AiProviderFactory
from app.api.dependencies import get_current_user, get_department_scope
from app.core.config import get_settings
from app.core.database import get_mongo_database
from app.core.field_labels_vi import sanitize_ai_text
from app.models.ai import AIChatRequest
from app.models.user import CurrentUser
from app.repositories.alert_repository import AlertRepository
from app.repositories.overload_repository import OverloadRepository
from app.repositories.performance_repository import PerformanceRepository
from app.services.ai_service import AiService

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])


def get_ai_service() -> AiService:
    database = get_mongo_database().get_database()
    return AiService(
        PerformanceRepository(database),
        AlertRepository(database),
        OverloadRepository(database),
        AiProviderFactory(get_settings()),
    )


def _sse(payload: dict[str, str]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream", summary="Trò chuyện với Trợ lý AI bằng SSE")
async def stream_ai_chat(
    request: AIChatRequest,
    scope=Depends(get_department_scope),
    _: CurrentUser = Depends(get_current_user),
    service: AiService = Depends(get_ai_service),
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        yield _sse({"type": "start"})
        try:
            async for chunk in service.stream_response(request.message, scope):
                safe_chunk = sanitize_ai_text(chunk)
                if safe_chunk:
                    yield _sse({"type": "token", "content": safe_chunk})
        except Exception:  # SSE boundary: keep provider/database faults inside this stream.
            yield _sse(
                {
                    "type": "error",
                    "content": "Trợ lý AI hiện chưa sẵn sàng. Vui lòng thử lại sau ít phút.",
                }
            )
        yield _sse({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
