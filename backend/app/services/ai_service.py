from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import Any

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.ai.factory import SAFE_AI_FALLBACK_MESSAGE, AiProviderFactory
from app.core.field_labels_vi import sanitize_ai_text, translate_metrics_to_vietnamese
from app.repositories.alert_repository import AlertRepository
from app.repositories.overload_repository import OverloadRepository
from app.repositories.performance_repository import PerformanceRepository


def _display_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


class AiService:
    def __init__(
        self,
        performance_repository: PerformanceRepository,
        alert_repository: AlertRepository,
        overload_repository: OverloadRepository,
        provider_factory: AiProviderFactory,
    ) -> None:
        self.performance_repository = performance_repository
        self.alert_repository = alert_repository
        self.overload_repository = overload_repository
        self.provider_factory = provider_factory

    async def build_scoped_context(self, scope: ObjectId | None) -> dict[str, Any]:
        """Read only already-authorized repositories; no client-supplied scope is trusted."""

        try:
            metrics = await self.performance_repository.find_many(scope)
            alerts = await self.alert_repository.find_many(scope, status="open")
            overload_logs = await self.overload_repository.list_logs(scope)
        except (PyMongoError, RuntimeError):
            return {
                "scope": "toàn công ty" if scope is None else "phòng ban của người dùng",
                "note": "Hiện chưa thể tải đầy đủ dữ liệu từ hệ thống.",
            }

        metric_data = [
            {
                "employee_id": _display_value(metric.employee_id),
                "date": _display_value(metric.date),
                "tasks_completed": metric.tasks_completed,
                "quality_score": metric.quality_score,
                "performance_score": metric.performance_score,
                "note": metric.note,
            }
            for metric in metrics[:60]
        ]
        alert_data = [
            {
                "employee_name": alert.employee_name,
                "alert_type": alert.alert_type,
                "severity": _display_value(alert.severity),
                "status": _display_value(alert.status),
                "title": alert.title,
                "message": alert.message,
                "suggested_action": alert.suggested_action,
            }
            for alert in alerts[:30]
        ]
        overload_data = [
            {
                "employee_id": _display_value(log.employee_id),
                "date": _display_value(log.date),
                "trigger_reason": log.trigger_reason,
                "tasks_completed": log.tasks_completed,
                "quality_score": log.quality_score,
                "baseline_quality_avg": log.baseline_quality_avg,
            }
            for log in overload_logs[:30]
        ]
        return {
            "scope": "toàn công ty" if scope is None else "phòng ban của người dùng",
            "performance_metrics": metric_data,
            "alerts": alert_data,
            "overload_logs": overload_data,
        }

    async def stream_response(self, message: str, scope: ObjectId | None) -> AsyncIterator[str]:
        context = await self.build_scoped_context(scope)
        translated_context = translate_metrics_to_vietnamese(context)
        prompt = (
            "Bạn là Trợ lý AI của hệ thống quản lý hiệu suất. Hãy trả lời bằng tiếng Việt phổ thông, "
            "ngắn gọn và có gợi ý hành động cụ thể nếu phù hợp. Chỉ sử dụng dữ liệu trong phạm vi "
            "được cung cấp. Không được nhắc đến tên trường kỹ thuật, mã nội bộ hoặc thông tin ngoài "
            "phạm vi. Nếu dữ liệu chưa đủ, hãy nói rõ là chưa có dữ liệu.\n\n"
            f"Dữ liệu đã được chuyển sang tiếng Việt:\n{translated_context}\n\n"
            f"Câu hỏi của người dùng:\n{sanitize_ai_text(message)}"
        )

        provider_output: list[str] = []
        try:
            async for chunk in self.provider_factory.generate_insight_stream(prompt):
                provider_output.append(chunk)
            safe_output = sanitize_ai_text("".join(provider_output))
            if safe_output:
                # Sanitize the complete provider output first so a raw field cannot be
                # reconstructed by joining two separately sanitized chunks.
                for start in range(0, len(safe_output), 160):
                    yield safe_output[start : start + 160]
                return
        except Exception:  # AI boundary: provider faults must never crash the API stream.
            yield SAFE_AI_FALLBACK_MESSAGE
            return
        yield SAFE_AI_FALLBACK_MESSAGE
