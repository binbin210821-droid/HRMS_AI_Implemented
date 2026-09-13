from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.ai.factory import AiProviderFactory
from app.ai.governance import AiAuditLogger
from app.ai.rag import CloudflareEmbeddingProvider, KnowledgeChunkRepository, RagService
from app.ai.tool_factory import AiToolProviderFactory
from app.api.dependencies import get_current_user, get_department_scope, require_role
from app.core.config import get_settings
from app.core.database import get_mongo_database
from app.core.field_labels_vi import sanitize_ai_text
from app.core.http_contract import get_request_id
from app.infrastructure.rate_limit import rate_limit_group
from app.models.ai import AIChatRequest
from app.models.ai_leadership import LeadershipAiContext
from app.models.ai_proposal import AiLeadershipProposalResponse
from app.models.ai_tools import AiToolPreviewRequest, AiToolPreviewResponse
from app.models.user import CurrentUser, UserRole
from app.repositories.ai_conversation_repository import AiConversationRepository
from app.repositories.alert_repository import AlertRepository
from app.repositories.coordination_repository import CoordinationRepository
from app.repositories.department_evaluation_repository import DepartmentEvaluationRepository
from app.repositories.overload_repository import OverloadRepository
from app.repositories.performance_repository import PerformanceRepository
from app.repositories.task_repository import TaskRepository
from app.services.ai_chat_orchestrator import AiChatOrchestrator
from app.services.ai_data_tool_service import AiDataToolService
from app.services.ai_leadership_context_service import AiLeadershipContextService
from app.services.ai_service import AiService
from app.services.ai_tool_service import AiToolService, build_tool_registry
from app.services.coordination_service import CoordinationService
from app.services.manager_briefing_service import ManagerBriefingService

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


def get_ai_service(request: Request) -> AiService:
    database = get_mongo_database().get_database()
    settings = get_settings()
    rag_service = RagService(
        CloudflareEmbeddingProvider(settings),
        KnowledgeChunkRepository(
            database,
            settings.ai_vector_index_name,
            settings.ai_rag_local_fallback_enabled,
        ),
        settings.ai_rag_enabled,
        settings.ai_rag_top_k,
    )
    audit_logger = AiAuditLogger(
        database["ai_audit_logs"], settings.ai_provider, settings.ai_model
    )
    performance_repository = PerformanceRepository(database)
    alert_repository = AlertRepository(database)
    overload_repository = OverloadRepository(database)
    return AiService(
        performance_repository,
        alert_repository,
        overload_repository,
        AiProviderFactory(settings),
        total_timeout_seconds=settings.ai_total_timeout_seconds,
        proposal_cache=getattr(request.app.state, "ai_proposal_cache", None),
        summary_cache=getattr(request.app.state, "ai_summary_cache", None),
        summary_context_max_chars=settings.ai_summary_context_max_chars,
        rag_service=rag_service,
        audit_logger=audit_logger,
        provider_name=settings.ai_provider,
        model=settings.ai_model,
        manager_briefing_service=ManagerBriefingService(
            performance_repository,
            alert_repository,
            overload_repository,
            TaskRepository(database),
        ),
        leadership_context_service=AiLeadershipContextService(
            AiDataToolService(
                performance_repository,
                alert_repository,
                overload_repository,
                TaskRepository(database),
                DepartmentEvaluationRepository(database),
            )
        ),
    )


def get_ai_tool_service() -> AiToolService:
    database = get_mongo_database().get_database()
    coordination_service = CoordinationService(CoordinationRepository(database))
    settings = get_settings()
    data_service = AiDataToolService(
        PerformanceRepository(database),
        AlertRepository(database),
        OverloadRepository(database),
        TaskRepository(database),
        DepartmentEvaluationRepository(database),
    )
    audit_logger = AiAuditLogger(
        database["ai_audit_logs"], settings.ai_provider, settings.ai_model
    )
    return AiToolService(
        coordination_service,
        AiToolProviderFactory(settings),
        build_tool_registry(coordination_service, audit_logger, data_service),
        audit_logger=audit_logger,
        provider_name=settings.ai_provider,
        model=settings.ai_model,
    )


def get_ai_leadership_context_service() -> AiLeadershipContextService:
    database = get_mongo_database().get_database()
    return AiLeadershipContextService(
        AiDataToolService(
            PerformanceRepository(database),
            AlertRepository(database),
            OverloadRepository(database),
            TaskRepository(database),
            DepartmentEvaluationRepository(database),
        )
    )


def get_ai_chat_tool_service() -> AiToolService | None:
    """Keep casual chat available while Mongo-backed tools are unavailable."""
    try:
        return get_ai_tool_service()
    except RuntimeError:
        return None


def _sse(payload: dict[str, str]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post(
    "/chat/stream",
    summary="Trò chuyện với Trợ lý AI bằng SSE",
    dependencies=[Depends(rate_limit_group("ai_chat"))],
)
async def stream_ai_chat(
    http_request: Request,
    request: AIChatRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    chat_service: AiService = Depends(get_ai_service),
    tool_service: AiToolService | None = Depends(get_ai_chat_tool_service),
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        yield _sse({"type": "start"})
        conversation_id = request.conversation_id or uuid4().hex
        conversation_repository = None
        try:
            conversation_repository = AiConversationRepository(get_mongo_database().get_database())
        except RuntimeError:
            # Casual chat and test doubles remain available when Mongo is not ready.
            pass
        conversation_context = None
        if request.conversation_id and conversation_repository is not None:
            conversation_context = await conversation_repository.get_context(
                request.conversation_id,
                current_user.user_id,
                scope,
            )
        yield _sse({"type": "conversation", "conversation_id": conversation_id})
        try:
            if request.mode == "chat" and (
                AiChatOrchestrator.requires_data_tool(request.message)
                or (
                    request.conversation_id is not None
                    and AiChatOrchestrator.is_follow_up(request.message)
                )
            ):
                yield _sse({"type": "status", "content": "Đang đọc dữ liệu hệ thống…"})
            if tool_service is None:
                try:
                    stream = chat_service.stream_response(
                        request.message,
                        scope,
                        current_user.user_id,
                        mode=request.mode,
                        request_id=get_request_id(http_request),
                        refresh=request.refresh,
                        role=current_user.role,
                    )
                except TypeError:
                    stream = chat_service.stream_response(request.message, scope)
            else:
                stream = AiChatOrchestrator(chat_service, tool_service).stream_response(
                    request.message,
                    scope,
                    current_user,
                    mode=request.mode,
                    request_id=get_request_id(http_request),
                    refresh=request.refresh,
                    conversation_id=conversation_id,
                    conversation_context=conversation_context,
                    conversation_repository=conversation_repository,
                )
            async for chunk in stream:
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


@router.post(
    "/tool-preview",
    response_model=AiToolPreviewResponse,
    summary="AI chọn công cụ đọc dữ liệu trong phạm vi phòng ban",
    dependencies=[Depends(rate_limit_group("ai_chat"))],
)
async def preview_ai_tool(
    request: AiToolPreviewRequest,
    scope=Depends(get_department_scope),
    current_user: CurrentUser = Depends(get_current_user),
    service: AiToolService = Depends(get_ai_tool_service),
) -> AiToolPreviewResponse:
    result_status, tool_name, data, message = await service.preview_from_message(
        request.message, current_user, scope
    )
    return AiToolPreviewResponse(
        status=result_status,
        tool_name=tool_name,
        data=data,
        message=message,
    )


@router.post(
    "/leadership-proposal",
    response_model=AiLeadershipProposalResponse,
    summary="Tạo bản nháp đề xuất AI cho Lãnh đạo",
    dependencies=[Depends(rate_limit_group("ai_chat"))],
)
async def generate_leadership_proposal(
    current_user: CurrentUser = Depends(require_role(UserRole.LEADERSHIP)),
    context_service: AiLeadershipContextService = Depends(get_ai_leadership_context_service),
    ai_service: AiService = Depends(get_ai_service),
) -> AiLeadershipProposalResponse:
    """Return a reviewable proposal; issuing a directive remains a separate action."""

    context: LeadershipAiContext = await context_service.build(current_user)
    return await ai_service.generate_leadership_action_proposal(
        context,
        actor_id=current_user.user_id,
    )
