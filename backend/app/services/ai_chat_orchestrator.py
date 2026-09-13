from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from bson import ObjectId

from app.models.user import CurrentUser, UserRole
from app.services.ai_service import AiService
from app.services.ai_tool_service import CONTEXT_REVALIDATION_MESSAGE, AiToolService

SAFE_DATA_ACCESS_MESSAGE = "Không thể truy cập dữ liệu hoặc dữ liệu nằm ngoài phạm vi quyền được cấp."
LEADERSHIP_DETAIL_POLICY_MESSAGE = (
    "Tôi có thể cung cấp số liệu tổng hợp theo phòng ban. "
    "Thông tin chi tiết từng nhân viên chỉ được hiển thị khi có nghiệp vụ được phép."
)
NO_OPEN_ALERTS_MESSAGE = (
    "Đã truy cập dữ liệu trong phạm vi của bạn nhưng hiện không có cảnh báo nào đang mở."
)
NO_MATCHING_DATA_MESSAGE = "Đã truy cập dữ liệu nhưng chưa có dữ liệu phù hợp với câu hỏi này."

_DATA_QUERY_MARKERS = (
    "dữ liệu",
    "hiệu suất",
    "điểm",
    "nhân viên nào",
    "phòng ban nào",
    "cảnh báo",
    "quá tải",
    "quá hạn",
    "trễ hạn",
    "nhiệm vụ",
    "công việc",
    "đánh giá tuần",
    "đánh giá",
    "xu hướng",
    "diễn biến",
    "so sánh",
    "so với",
    "tuần trước",
    "tốt hơn",
    "tiến bộ",
    "giải thích cảnh báo",
    "gần đây",
    "chú ý",
    "thống kê",
    "bao nhiêu",
    "performance",
    "alert",
    "overdue",
    "employee",
    "department",
)


class AiChatOrchestrator:
    """Selects a read-only data tool before generating a grounded answer."""

    def __init__(self, chat_service: AiService, tool_service: AiToolService) -> None:
        self.chat_service = chat_service
        self.tool_service = tool_service

    @staticmethod
    def requires_data_tool(message: str) -> bool:
        normalized = message.casefold()
        return any(marker in normalized for marker in _DATA_QUERY_MARKERS)

    @staticmethod
    def is_follow_up(message: str) -> bool:
        normalized = message.casefold().strip()
        return any(
            marker in normalized
            for marker in ("vì sao", "tại sao", "nên làm gì", "so với lần trước", "giải thích thêm")
        )

    async def stream_response(
        self,
        message: str,
        scope: ObjectId | None,
        current_user: CurrentUser,
        *,
        mode: str = "chat",
        request_id: str | None = None,
        refresh: bool = False,
        conversation_id: str | None = None,
        conversation_context: dict[str, Any] | None = None,
        conversation_repository: Any | None = None,
    ) -> AsyncIterator[str]:
        if current_user.role == UserRole.LEADERSHIP and _is_restricted_detail_request(message):
            yield LEADERSHIP_DETAIL_POLICY_MESSAGE
            return
        use_previous_context = bool(
            mode == "chat"
            and conversation_context
            and self.is_follow_up(message)
        )
        if mode != "chat" or (
            not self.requires_data_tool(message) and not use_previous_context
        ):
            async for chunk in self._stream_legacy(
                message,
                scope,
                current_user.user_id,
                current_user.role,
                mode,
                request_id,
                refresh,
            ):
                yield chunk
            return

        if use_previous_context:
            status, tool_name, data, _message = await self.tool_service.read_data_from_context(
                conversation_context or {},
                current_user,
                scope,
                conversation_id=conversation_id,
                conversation_repository=conversation_repository,
            )
        else:
            status, tool_name, data, _message = await self._read_message(
                message,
                current_user,
                scope,
                conversation_id=conversation_id,
                conversation_repository=conversation_repository,
            )

            expected_tool = self._deterministic_tool_name(message, current_user.role)
            if expected_tool and (
                tool_name != expected_tool
                or status == "no_tool_call"
                or not _data_rows(data)
            ):
                status, tool_name, data, _message = await self._read_message(
                    message,
                    current_user,
                    scope,
                    conversation_id=conversation_id,
                    conversation_repository=conversation_repository,
                    force_deterministic=True,
                )
                rows = _data_rows(data)
        if status == "context_invalid":
            yield _message or CONTEXT_REVALIDATION_MESSAGE
            return
        rows = _data_rows(data)
        if status != "executed":
            yield (
                _message
                if _message == LEADERSHIP_DETAIL_POLICY_MESSAGE
                else SAFE_DATA_ACCESS_MESSAGE
            )
            return
        if not rows:
            yield (
                NO_OPEN_ALERTS_MESSAGE
                if tool_name == "get_open_alerts"
                else NO_MATCHING_DATA_MESSAGE
            )
            return

        grounded_data = _remove_internal_fields(data)
        async for chunk in self.chat_service.stream_grounded_response(
            message,
            scope,
            current_user.user_id,
            tool_name or "unknown",
            grounded_data,
            request_id=request_id,
        ):
            yield chunk

    def _deterministic_tool_name(self, message: str, role=None) -> str | None:
        resolver = getattr(self.tool_service, "deterministic_tool_name", None)
        if not callable(resolver):
            return None
        try:
            return resolver(message, role)
        except TypeError:
            # Compatibility for older test doubles and adapters.
            return resolver(message)

    async def _read_message(
        self,
        message: str,
        current_user: CurrentUser,
        scope: ObjectId | None,
        *,
        conversation_id: str | None,
        conversation_repository: Any | None,
        force_deterministic: bool = False,
    ):
        try:
            return await self.tool_service.read_data_from_message(
                message,
                current_user,
                scope,
                conversation_id=conversation_id,
                conversation_repository=conversation_repository,
                force_deterministic=force_deterministic,
            )
        except TypeError as error:
            # Compatibility for small test doubles and older adapters while the
            # optional recovery argument rolls out.
            if "unexpected keyword argument" not in str(error):
                raise
            return await self.tool_service.read_data_from_message(
                message,
                current_user,
                scope,
            )

    async def _stream_legacy(
        self,
        message: str,
        scope: ObjectId | None,
        actor_id: str,
        role: UserRole,
        mode: str,
        request_id: str | None,
        refresh: bool,
    ) -> AsyncIterator[str]:
        try:
            stream = self.chat_service.stream_response(
                message,
                scope,
                actor_id,
                mode=mode,
                request_id=request_id,
                refresh=refresh,
                role=role,
            )
        except TypeError:
            stream = self.chat_service.stream_response(message, scope)
        async for chunk in stream:
            yield chunk


def _remove_internal_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _remove_internal_fields(item)
            for key, item in value.items()
            if key.casefold() not in {"id", "_id", "employee_id", "department_id", "alert_id"}
        }
    if isinstance(value, list):
        return [_remove_internal_fields(item) for item in value]
    return value


def _data_rows(data: Any) -> list[Any]:
    if not isinstance(data, dict):
        return []
    rows = data.get("du_lieu")
    return rows if isinstance(rows, list) else []


def _is_restricted_detail_request(message: str) -> bool:
    normalized = message.casefold()
    return any(
        marker in normalized
        for marker in (
            "chi tiết từng nhân viên",
            "từng nhân viên",
            "tên nhân viên",
            "người phụ trách",
            "số điện thoại",
            "địa chỉ",
            "email nhân viên",
            "lương nhân viên",
        )
    )


__all__ = [
    "LEADERSHIP_DETAIL_POLICY_MESSAGE",
    "NO_MATCHING_DATA_MESSAGE",
    "NO_OPEN_ALERTS_MESSAGE",
    "SAFE_DATA_ACCESS_MESSAGE",
    "AiChatOrchestrator",
]
