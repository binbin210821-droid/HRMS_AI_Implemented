from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
from collections import Counter, defaultdict
from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import Any

from bson import ObjectId
from pydantic import ValidationError
from pymongo.errors import PyMongoError

from app.ai.base import AI_SUMMARY_MODE_MARKER, JSON_OBJECT_MODE_MARKER
from app.ai.cache import AiProposalCache, AiSummaryCache
from app.ai.factory import SAFE_AI_FALLBACK_MESSAGE, AiProviderFactory
from app.ai.governance import AiAuditLogger
from app.ai.rag import RagService
from app.core.field_labels_vi import sanitize_ai_text, translate_metrics_to_vietnamese
from app.core.time import BusinessClock
from app.models.ai_leadership import LeadershipAiContext
from app.models.ai_proposal import (
    AiAlertProposalResponse,
    AiLeadershipProposalResponse,
    ApplyCoordinationProposal,
    CrossDepartmentCoordinationProposal,
    IssueDepartmentDirectiveProposal,
    LeadershipFollowUpProposal,
    ResolveAlertProposal,
    ThresholdConfigProposal,
)
from app.models.alert import AlertDocument
from app.models.overload import WorkloadCandidateResponse
from app.models.task_planning import (
    AiTaskPlanningExplanation,
    OverdueTaskPlanningResponse,
)
from app.models.user import UserRole
from app.repositories.alert_repository import AlertRepository
from app.repositories.overload_repository import OverloadRepository
from app.repositories.performance_repository import PerformanceRepository
from app.services.ai_leadership_context_service import AiLeadershipContextService
from app.services.manager_briefing_service import ManagerBriefingService

logger = logging.getLogger(__name__)

GROUNDED_PROVIDER_FAILURE_MESSAGE = (
    "Đã đọc được dữ liệu trong phạm vi của bạn, nhưng Trợ lý AI chưa thể diễn giải lúc này."
    " Bạn có thể thử lại sau ít phút."
)


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
        total_timeout_seconds: float = 60.0,
        proposal_cache: AiProposalCache | None = None,
        summary_cache: AiSummaryCache | None = None,
        summary_context_max_chars: int = 24000,
        rag_service: RagService | None = None,
        audit_logger: AiAuditLogger | None = None,
        provider_name: str = "unknown",
        model: str = "unknown",
        manager_briefing_service: ManagerBriefingService | None = None,
        leadership_context_service: AiLeadershipContextService | None = None,
        clock: BusinessClock | None = None,
    ) -> None:
        self.performance_repository = performance_repository
        self.alert_repository = alert_repository
        self.overload_repository = overload_repository
        self.provider_factory = provider_factory
        self.total_timeout_seconds = max(0.1, total_timeout_seconds)
        self.proposal_cache = proposal_cache or AiProposalCache()
        self.summary_cache = summary_cache or AiSummaryCache()
        self.summary_context_max_chars = max(1000, summary_context_max_chars)
        self.rag_service = rag_service
        self.audit_logger = audit_logger
        self.provider_name = provider_name
        self.model = model
        self.manager_briefing_service = manager_briefing_service
        self.leadership_context_service = leadership_context_service
        self.clock = clock or BusinessClock()

    async def _collect_provider_output(
        self, prompt: str, request_id: str | None = None
    ) -> str:
        chunks: list[str] = []
        async with asyncio.timeout(self.total_timeout_seconds):
            try:
                stream = self.provider_factory.generate_insight_stream(
                    prompt, request_id=request_id
                )
            except TypeError:
                # Keep small fake providers and older adapters source-compatible while
                # the production factory carries the request correlation id.
                stream = self.provider_factory.generate_insight_stream(prompt)
            async for chunk in stream:
                chunks.append(chunk)
        return "".join(chunks)

    async def build_scoped_context(self, scope: ObjectId | None) -> dict[str, Any]:
        """Read only already-authorized repositories; no client-supplied scope is trusted."""

        try:
            metrics = await self._bounded_read(self.performance_repository.find_many, scope, 60)
            alerts = await self._bounded_read(
                self.alert_repository.find_many, scope, 30, status="open"
            )
            overload_logs = await self._bounded_read(self.overload_repository.list_logs, scope, 30)
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

    @staticmethod
    async def _bounded_read(
        method: Any, scope: ObjectId | None, limit: int, **kwargs: Any
    ) -> Any:
        """Giới hạn dữ liệu đưa vào AI, vẫn tương thích adapter test nhỏ."""
        if "limit" in inspect.signature(method).parameters:
            return await method(scope, limit=limit, **kwargs)
        return await method(scope, **kwargs)

    async def build_summary_context(
        self, scope: ObjectId | None, max_chars: int = 24000
    ) -> dict[str, Any]:
        """Build a compact aggregate context for the dashboard summary only."""

        if self.manager_briefing_service is not None:
            return await self.manager_briefing_service.build(scope, max_chars)

        try:
            metrics = await self._bounded_read(self.performance_repository.find_many, scope, 60)
            alerts = await self._bounded_read(
                self.alert_repository.find_many, scope, 30, status="open"
            )
            overload_logs = await self._bounded_read(self.overload_repository.list_logs, scope, 30)
        except (PyMongoError, RuntimeError):
            return {
                "scope": "toàn công ty" if scope is None else "phòng ban của người dùng",
                "note": "Hiện chưa thể tải đầy đủ dữ liệu từ hệ thống.",
            }

        employees = {
            str(getattr(metric, "employee_id", ""))
            for metric in metrics
            if getattr(metric, "employee_id", None) is not None
        }
        daily: defaultdict[str, list[float]] = defaultdict(list)
        for metric in metrics:
            metric_date = getattr(metric, "date", None)
            performance_score = getattr(metric, "performance_score", None)
            if metric_date is not None and performance_score is not None:
                daily[str(metric_date)].append(float(performance_score))

        severity_counts = Counter(str(getattr(alert, "severity", "unknown")) for alert in alerts)
        compact_alerts = [
            {
                "employee_name": getattr(alert, "employee_name", ""),
                "alert_type": getattr(alert, "alert_type", ""),
                "severity": _display_value(getattr(alert, "severity", "")),
                "title": getattr(alert, "title", ""),
                "message": getattr(alert, "message", ""),
            }
            for alert in alerts[:5]
        ]
        performance_values = [
            float(metric.performance_score)
            for metric in metrics
            if getattr(metric, "performance_score", None) is not None
        ]
        quality_values = [
            float(metric.quality_score)
            for metric in metrics
            if getattr(metric, "quality_score", None) is not None
        ]
        context: dict[str, Any] = {
            "scope": "toàn công ty" if scope is None else "phòng ban của người dùng",
            "employee_count": len(employees),
            "metric_days": len(daily),
            "average_performance_score": (
                round(sum(performance_values) / len(performance_values), 2)
                if performance_values
                else None
            ),
            "average_quality_score": (
                round(sum(quality_values) / len(quality_values), 2)
                if quality_values
                else None
            ),
            "alerts": {
                "total": len(alerts),
                "by_severity": dict(severity_counts),
                "top_items": compact_alerts,
            },
            "overload_logs": {
                "total": len(overload_logs),
                "employee_count": len(
                    {
                        str(getattr(log, "employee_id", ""))
                        for log in overload_logs
                        if getattr(log, "employee_id", None) is not None
                    }
                ),
            },
            "recent_trend": [
                {"date": day, "average_performance_score": round(sum(values) / len(values), 2)}
                for day, values in sorted(daily.items())[-7:]
            ],
        }
        rendered = translate_metrics_to_vietnamese(context)
        if len(rendered) > max(1000, max_chars):
            context["alerts"]["top_items"] = compact_alerts[:2]
            context["recent_trend"] = context["recent_trend"][-3:]
        return context

    async def _generate_text(self, prompt: str, request_id: str | None) -> str:
        try:
            output = sanitize_ai_text(await self._collect_provider_output(prompt, request_id))
            if output == SAFE_AI_FALLBACK_MESSAGE:
                logger.warning(
                    "ai_text_generation_failure %s",
                    json.dumps(
                        {
                            "request_id": request_id,
                            "provider": self.provider_name,
                            "model": self.model,
                            "error_type": "provider_fallback",
                        },
                        sort_keys=True,
                    ),
                )
                return ""
            if output:
                return output
            logger.warning(
                "ai_text_generation_failure %s",
                json.dumps(
                    {
                        "request_id": request_id,
                        "provider": self.provider_name,
                        "model": self.model,
                        "error_type": "empty_output",
                    },
                    sort_keys=True,
                ),
            )
        except Exception as error:
            logger.warning(
                "ai_text_generation_failure %s",
                json.dumps(
                    {
                        "request_id": request_id,
                        "provider": self.provider_name,
                        "model": self.model,
                        "error_type": type(error).__name__,
                    },
                    sort_keys=True,
                ),
            )
            return ""
        return ""

    @staticmethod
    def _render_grounded_fallback(
        message: str, tool_name: str, tool_data: dict[str, Any]
    ) -> str:
        """Render already-authorized data locally when the text model is unavailable."""

        summary = tool_data.get("tong_quan")
        if not isinstance(summary, dict):
            return GROUNDED_PROVIDER_FAILURE_MESSAGE

        if tool_name == "get_performance_trend":
            direction = summary.get("Xu hướng", "chưa xác định")
            period = tool_data.get("ky_du_lieu") or {}
            lines = [
                f"Kết luận: Xu hướng hiệu suất đang {direction}.",
                "Bằng chứng:",
                f"• Điểm đầu kỳ: {summary.get('Điểm hiệu suất đầu kỳ')}",
                f"• Điểm cuối kỳ: {summary.get('Điểm hiệu suất cuối kỳ')}",
                f"• Thay đổi: {summary.get('Thay đổi điểm hiệu suất')}",
                f"• Điểm chất lượng trung bình: {summary.get('Điểm chất lượng trung bình')}",
                f"Kỳ dữ liệu: {period.get('tu_ngay')} đến {period.get('den_ngay')}",
                "Đề xuất: Theo dõi thêm các ngày tiếp theo và kiểm tra khối lượng công việc nếu xu hướng giảm.",
            ]
            return sanitize_ai_text("\n".join(lines))

        if tool_name == "compare_performance_periods":
            current = summary.get("Kỳ hiện tại") or {}
            previous = summary.get("Kỳ trước") or {}
            lines = [
                f"Kết luận: Điểm hiệu suất thay đổi {summary.get('Thay đổi điểm hiệu suất')}, "
                f"tương đương {summary.get('Thay đổi phần trăm')}%.",
                "Bằng chứng:",
                f"• Kỳ hiện tại: {current.get('Điểm hiệu suất trung bình')}",
                f"• Kỳ trước: {previous.get('Điểm hiệu suất trung bình')}",
                f"• Chất lượng kỳ hiện tại: {current.get('Điểm chất lượng trung bình')}",
                f"• Chất lượng kỳ trước: {previous.get('Điểm chất lượng trung bình')}",
                f"Kỳ dữ liệu: {current.get('Từ ngày')} đến {current.get('Đến ngày')} so với "
                f"{previous.get('Từ ngày')} đến {previous.get('Đến ngày')}.",
                "Đề xuất: Kiểm tra các nhân viên có mức thay đổi lớn trước khi điều chỉnh phân công.",
            ]
            return sanitize_ai_text("\n".join(lines))

        if tool_name == "explain_alert":
            rows = tool_data.get("du_lieu")
            if not isinstance(rows, list) or not rows:
                return GROUNDED_PROVIDER_FAILURE_MESSAGE
            lines = [f"Kết luận: Có {len(rows)} cảnh báo đang mở cần xem xét.", "Bằng chứng:"]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                lines.extend(
                    [
                        f"• {row.get('Nhân viên', 'Nhân viên chưa xác định')}: {row.get('Tiêu đề')}",
                        f"  Mức độ: {row.get('Mức độ')}; Nội dung: {row.get('Nội dung')}",
                        f"  Ngày phát hiện: {row.get('Ngày phát hiện')}",
                    ]
                )
            lines.extend(
                [
                    "Kỳ dữ liệu: các ngày phát hiện trong cảnh báo và chỉ số liên quan gần nhất.",
                    "Đề xuất: Kiểm tra cảnh báo trong màn hình Cảnh báo trước khi áp dụng hành động.",
                ]
            )
            return sanitize_ai_text("\n".join(lines))

        if tool_name in {
            "get_company_performance_summary",
            "compare_departments",
            "get_department_risk_summary",
            "get_manager_evaluations",
            "get_overdue_work_summary",
            "get_cross_department_coordination_candidates",
        }:
            return AiService._render_leadership_grounded_fallback(tool_name, tool_data)

        if tool_name != "get_department_performance":
            return GROUNDED_PROVIDER_FAILURE_MESSAGE

        lines = [f"{summary.get('Phòng ban', 'Phòng ban')}:"]
        lines.extend(
            [
                f"• Điểm hiệu suất trung bình: {summary.get('Điểm hiệu suất trung bình')}",
                f"• Điểm chất lượng trung bình: {summary.get('Điểm chất lượng trung bình')}",
                f"• Số nhân viên có ghi nhận: {summary.get('Số nhân viên có ghi nhận')}",
                f"• Số ngày có ghi nhận: {summary.get('Số ngày có ghi nhận')}",
            ]
        )

        normalized = message.casefold()
        asks_average = "trung bình" in normalized or "bao nhiêu" in normalized
        rows = tool_data.get("du_lieu")
        if not asks_average and isinstance(rows, list):
            lines.append("\nChi tiết theo nhân viên:")
            for row in rows:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    "• "
                    f"{row.get('Nhân viên', 'Nhân viên chưa xác định')}: "
                    f"hiệu suất {row.get('Điểm hiệu suất trung bình')}, "
                    f"chất lượng {row.get('Điểm chất lượng trung bình')}, "
                    f"{row.get('Số ngày có ghi nhận')} ngày ghi nhận"
                )
        return sanitize_ai_text("\n".join(lines))

    @staticmethod
    def _render_leadership_grounded_fallback(
        tool_name: str, tool_data: dict[str, Any]
    ) -> str:
        """Render Leadership aggregates when the text provider is unavailable."""

        rows = [row for row in tool_data.get("du_lieu", []) if isinstance(row, dict)]
        summary = tool_data.get("tong_quan") or {}
        period = tool_data.get("ky_du_lieu") or {}
        period_start = period.get("tu_ngay") or summary.get("Từ ngày")
        period_end = period.get("den_ngay") or summary.get("Đến ngày")
        period_label = (
            f"{period_start} đến {period_end}"
            if period_start and period_end
            else "kỳ dữ liệu gần nhất"
        )

        if not rows:
            return sanitize_ai_text(
                "Đã đọc dữ liệu tổng hợp toàn công ty nhưng chưa có bản ghi phù hợp "
                "với câu hỏi trong kỳ dữ liệu này."
            )

        if tool_name in {"get_company_performance_summary", "compare_departments"}:
            lines = [
                "Kết luận: Đây là kết quả so sánh hiệu suất tổng hợp theo phòng ban.",
                "Bằng chứng:",
            ]
            for row in rows:
                trend = {
                    "increasing": "đang tăng",
                    "decreasing": "đang giảm",
                    "stable": "ổn định",
                    "insufficient_data": "chưa đủ dữ liệu xu hướng",
                }.get(str(row.get("Xu hướng")), "chưa xác định")
                lines.append(
                    f"• {row.get('Phòng ban', 'Phòng ban chưa xác định')}: "
                    f"hiệu suất {row.get('Điểm hiệu suất trung bình', 'chưa có dữ liệu')}, "
                    f"chất lượng {row.get('Điểm chất lượng trung bình', 'chưa có dữ liệu')}, "
                    f"{row.get('Số nhân viên', 0)} nhân viên, xu hướng {trend}."
                )
            lines.extend(
                [
                    f"Kỳ dữ liệu: {period_label}.",
                    "Gợi ý: Ưu tiên trao đổi với phòng ban có điểm giảm hoặc chưa đủ dữ liệu "
                    "trước khi đưa ra quyết định điều hành.",
                ]
            )
            return sanitize_ai_text("\n".join(lines))

        if tool_name == "get_manager_evaluations":
            lines = [
                f"Kết luận: Có {len(rows)} kỳ đánh giá Quản lý trong {period_label}.",
                "Bằng chứng:",
            ]
            for row in rows:
                lines.append(
                    f"• {row.get('Quản lý', 'Chưa xác định')} — "
                    f"{row.get('Phòng ban', 'Phòng ban chưa xác định')}: "
                    f"điểm tổng thể {row.get('Điểm đánh giá tổng thể', 'chưa có dữ liệu')}, "
                    f"hiệu suất phòng ban {row.get('Điểm hiệu suất trung bình phòng ban', 'chưa có dữ liệu')}, "
                    f"điểm đúng hạn {row.get('Điểm đúng hạn', 'chưa có dữ liệu')}."
                )
                note = row.get("Nhận xét")
                if note:
                    lines.append(f"  Nhận xét: {note}")
            lines.extend(
                [
                    f"Kỳ dữ liệu: {period_label}.",
                    "Gợi ý: Xem đồng thời hiệu suất phòng ban, khả năng hoàn thành đúng hạn "
                    "và việc thực hiện chỉ thị khi đánh giá.",
                ]
            )
            return sanitize_ai_text("\n".join(lines))

        if tool_name == "get_department_risk_summary":
            lines = [
                f"Kết luận: Có {len(rows)} phòng ban cần chú ý về vận hành.",
                "Bằng chứng:",
            ]
            for row in rows:
                lines.append(
                    f"• {row.get('Phòng ban', 'Phòng ban chưa xác định')}: "
                    f"{row.get('Số cảnh báo đang mở', 0)} cảnh báo đang mở, "
                    f"{row.get('Số công việc quá hạn', 0)} công việc quá hạn, "
                    f"quá hạn lâu nhất {row.get('Số ngày quá hạn lớn nhất', 0)} ngày, "
                    f"mức độ cao nhất {row.get('Mức độ cao nhất') or 'chưa có'}."
                )
            lines.extend(
                [
                    f"Kỳ dữ liệu: {period_label}.",
                    "Gợi ý: Kiểm tra trước các phòng ban có cảnh báo mức cao hoặc nhiều việc quá hạn.",
                ]
            )
            return sanitize_ai_text("\n".join(lines))

        if tool_name == "get_overdue_work_summary":
            total_overdue = summary.get("Tổng số công việc quá hạn")
            total_undirected = summary.get("Tổng số công việc quá hạn chưa gửi chỉ thị")
            lines = [
                f"Kết luận: Toàn công ty có {total_overdue or 0} công việc quá hạn "
                f"tại {summary.get('Số phòng ban có việc quá hạn', len(rows))} phòng ban.",
                "Bằng chứng:",
            ]
            for row in rows:
                lines.append(
                    f"• {row.get('Phòng ban', 'Phòng ban chưa xác định')}: "
                    f"{row.get('Số công việc quá hạn', 0)} công việc quá hạn, "
                    f"{row.get('Số nhân viên liên quan', 0)} nhân viên liên quan, "
                    f"quá hạn lâu nhất {row.get('Số ngày quá hạn lớn nhất', 0)} ngày."
                )
            if total_undirected is not None:
                lines.append(
                    f"Trong đó có {total_undirected} công việc quá hạn chưa gửi chỉ thị."
                )
            lines.extend(
                [
                    f"Kỳ dữ liệu: {period_label}.",
                    "Gợi ý: Yêu cầu Quản lý các phòng ban này rà soát và cập nhật kế hoạch xử lý.",
                ]
            )
            return sanitize_ai_text("\n".join(lines))

        lines = [
            f"Kết luận: Có {len(rows)} phương án hỗ trợ liên phòng ban đủ điều kiện.",
            "Bằng chứng:",
        ]
        for row in rows:
            lines.append(
                f"• {row.get('Phòng ban nguồn', 'Phòng ban nguồn')} có thể nhận hỗ trợ từ "
                f"{row.get('Phòng ban hỗ trợ', 'phòng ban hỗ trợ')}: "
                f"mức độ phù hợp {row.get('Mức độ phù hợp', 'chưa có dữ liệu')}/100, "
                f"khả năng nhận thêm việc {row.get('Khả năng nhận thêm việc', 'chưa có dữ liệu')}/100, "
                f"khả năng hoàn thành đúng hạn {row.get('Khả năng hoàn thành đúng hạn', 'chưa có dữ liệu')}/100."
            )
        lines.extend(
            [
                f"Kỳ dữ liệu: {period_label}.",
                "Gợi ý: Đây là phương án tham khảo; cần Quản lý và Lãnh đạo xác nhận trước khi điều phối.",
            ]
        )
        return sanitize_ai_text("\n".join(lines))

    async def _build_chat_prompt(
        self,
        message: str,
        scope: ObjectId | None,
        mode: str,
        role: UserRole | None = None,
    ) -> str:
        context: Any
        rag_context: str
        marker: str
        if role == UserRole.LEADERSHIP:
            if self.leadership_context_service is None:
                context = {
                    "Phạm vi": "toàn công ty",
                    "Giới hạn dữ liệu": ["Chưa cấu hình context tổng hợp cho Lãnh đạo."],
                }
            else:
                leadership_context = await self.leadership_context_service.build_for_leadership()
                context = leadership_context.to_prompt_data()
            if mode == "summary":
                rag_context = "Không dùng kho tri thức cho bản tóm tắt Dashboard."
                marker = f"{AI_SUMMARY_MODE_MARKER}\n"
            else:
                rag_context = (
                    RagService.prompt_context(await self.rag_service.retrieve(message, scope))
                    if self.rag_service is not None
                    else "Chưa bật kho tri thức chính sách."
                )
                marker = ""
        elif mode == "summary":
            context = translate_metrics_to_vietnamese(
                await self.build_summary_context(scope, self.summary_context_max_chars)
            )
            rag_context = "Không dùng kho tri thức cho bản tóm tắt Dashboard."
            marker = f"{AI_SUMMARY_MODE_MARKER}\n"
        else:
            context = translate_metrics_to_vietnamese(await self.build_scoped_context(scope))
            rag_context = (
                RagService.prompt_context(await self.rag_service.retrieve(message, scope))
                if self.rag_service is not None
                else "Chưa bật kho tri thức chính sách."
            )
            marker = ""
        return (
            f"{marker}Bạn là Trợ lý AI của hệ thống quản lý hiệu suất. Hãy trả lời bằng tiếng Việt phổ thông, "
            "ngắn gọn và có gợi ý hành động cụ thể nếu phù hợp. Hãy phân loại câu hỏi trước khi trả lời: "
            "với câu hỏi về hiệu suất, cảnh báo, quá tải, công việc hoặc dữ liệu HRMS, chỉ sử dụng dữ liệu "
            "đã được cung cấp trong đúng phạm vi quyền; không suy đoán dữ liệu nghiệp vụ còn thiếu. "
            "Với câu hỏi hội thoại thông thường hoặc kiến thức phổ thông không cần dữ liệu HRMS, hãy tự "
            "trả lời tự nhiên bằng kiến thức của mô hình, không trả lời máy móc rằng chưa có dữ liệu. "
            "Với thông tin cần dữ liệu thời gian thực như thời tiết, giá cả hoặc tin tức, không được bịa; "
            "hãy nói rõ giới hạn hiện tại và hỏi thêm địa điểm/thời điểm nếu cần tích hợp nguồn dữ liệu. "
            "Không được nhắc đến tên trường kỹ thuật, mã nội bộ hoặc thông tin nhân sự ngoài phạm vi. "
            "Nếu câu hỏi HRMS thiếu dữ liệu cần thiết, hãy nói rõ là chưa có dữ liệu. "
            + (
                "Với bản tóm tắt Dashboard, bắt buộc trình bày theo bốn mục: Tổng quan, "
                "Tình trạng vận hành, Xu hướng gần đây và Gợi ý hành động; mỗi mục ở một dòng riêng. "
                if mode == "summary"
                else ""
            )
            + "\n\n"
            f"Dữ liệu đã được chuyển sang tiếng Việt:\n{context}\n\n"
            "Trích đoạn tài liệu chính sách liên quan (chỉ dùng nếu có):\n"
            f"{rag_context}\n\n"
            f"Câu hỏi của người dùng:\n{sanitize_ai_text(message)}"
        )

    async def stream_response(
        self,
        message: str,
        scope: ObjectId | None,
        actor_id: str | None = None,
        *,
        mode: str = "chat",
        request_id: str | None = None,
        refresh: bool = False,
        role: UserRole | None = None,
    ) -> AsyncIterator[str]:
        simple_answer = self._simple_chat_answer(message, role)
        if simple_answer is not None:
            await self._audit(
                actor_id,
                scope,
                "chat",
                message,
                simple_answer,
                "success",
                {"mode": mode, "deterministic": True},
            )
            yield simple_answer
            return

        prompt = await self._build_chat_prompt(message, scope, mode, role)
        summary_key = None
        if mode == "summary" and actor_id:
            summary_key = AiSummaryCache.build_key(
                actor_id,
                scope,
                self.clock.today().isoformat(),
            )

        if summary_key is not None:
            safe_output = await self.summary_cache.get_or_create(
                summary_key,
                lambda: self._generate_text(prompt, request_id),
                force_refresh=refresh,
            )
        else:
            safe_output = await self._generate_text(prompt, request_id)

        try:
            if safe_output:
                await self._audit(
                    actor_id,
                    scope,
                    "chat",
                    message,
                    safe_output,
                    "success",
                    {"mode": mode, "rag_enabled": self.rag_service is not None},
                )
                # Sanitize the complete provider output first so a raw field cannot be
                # reconstructed by joining two separately sanitized chunks.
                for start in range(0, len(safe_output), 160):
                    yield safe_output[start : start + 160]
                return
        except Exception:  # Governance failures must never crash the API stream.
            pass
        await self._audit(actor_id, scope, "chat", message, "", "fallback")
        yield SAFE_AI_FALLBACK_MESSAGE

    def _simple_chat_answer(
        self, message: str, role: UserRole | None
    ) -> str | None:
        """Answer safe, factual session questions without asking the model to guess."""

        normalized = message.casefold().strip()
        if (
            "hôm nay" in normalized
            and any(
                marker in normalized
                for marker in ("ngày mấy", "ngày bao nhiêu", "thứ mấy")
            )
        ):
            current_date = self.clock.today()
            return (
                f"Hôm nay là {current_date.day:02d}/{current_date.month:02d}/"
                f"{current_date.year}."
            )

        if any(
            marker in normalized
            for marker in (
                "chức vụ nào",
                "chức vụ của tôi",
                "vai trò nào",
                "vai trò của tôi",
            )
        ):
            role_labels = {
                UserRole.MANAGER: "Quản lý phòng ban",
                UserRole.LEADERSHIP: "Lãnh đạo",
            }
            role_label = role_labels.get(role) if role is not None else None
            if role_label is not None:
                return f"Bạn đang sử dụng vai trò {role_label}."

        return None

    async def stream_grounded_response(
        self,
        message: str,
        scope: ObjectId | None,
        actor_id: str | None,
        tool_name: str,
        tool_data: dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> AsyncIterator[str]:
        """Answer only from a validated, already-authorized tool result."""

        prompt = (
            "Bạn là Trợ lý AI của hệ thống quản lý hiệu suất. Hãy trả lời bằng tiếng Việt phổ thông, "
            "ngắn gọn, có cấu trúc dễ đọc và chỉ dựa trên kết quả công cụ đọc dữ liệu bên dưới. "
            "Nếu liệt kê nhiều nhân viên, hãy đặt tiêu đề ở dòng riêng và đưa mỗi nhân viên thành "
            "một dòng riêng bắt đầu bằng dấu •; ghi rõ điểm hiệu suất, điểm chất lượng và số ngày "
            "ghi nhận nếu có. Không dùng bảng Markdown, không dồn nhiều mục vào cùng một đoạn, "
            "không dùng ký hiệu ** hoặc * để định dạng. "
            "Với câu hỏi về xu hướng hoặc so sánh, trình bày theo các mục Kết luận, Bằng chứng, "
            "Kỳ dữ liệu và Đề xuất. Chỉ dùng các thay đổi/phần trăm đã có trong dữ liệu, không tự "
            "tính lại từ số liệu đã rút gọn. "
            "Không được suy đoán, "
            "bịa thêm nhân viên, số liệu hoặc phòng ban. Không nhắc tên công cụ, mã nội bộ hay tên "
            "trường kỹ thuật. Nếu kết quả không đủ để kết luận, hãy nói rõ chưa đủ dữ liệu.\n\n"
            f"Kết quả dữ liệu đã được kiểm tra quyền truy cập:\n"
            f"{json.dumps(tool_data, ensure_ascii=False, default=_display_value)}\n\n"
            f"Câu hỏi của người dùng:\n{sanitize_ai_text(message)}"
        )
        safe_output = await self._generate_text(prompt, request_id)
        if safe_output:
            await self._audit(
                actor_id,
                scope,
                "data_tool_chat",
                message,
                safe_output,
                "success",
                {"tool_name": tool_name, "grounded": True},
            )
            for start in range(0, len(safe_output), 160):
                yield safe_output[start : start + 160]
            return
        await self._audit(
            actor_id,
            scope,
            "data_tool_chat",
            message,
            "",
            "provider_fallback",
            {"tool_name": tool_name, "grounded": True, "data_read": True},
        )
        yield self._render_grounded_fallback(message, tool_name, tool_data)

    async def _audit(
        self,
        actor_id: str | None,
        scope: ObjectId | None,
        request_type: str,
        input_text: str,
        output_text: str,
        status: str,
        output_summary: dict[str, Any] | None = None,
    ) -> None:
        if self.audit_logger is None:
            return
        await self.audit_logger.record(
            actor_id=actor_id,
            department_id=scope,
            provider=self.provider_name,
            model=self.model,
            request_type=request_type,
            input_text=input_text,
            output_text=output_text,
            status=status,
            output_summary=output_summary,
        )

    @staticmethod
    def _extract_json(raw_output: str) -> dict[str, Any]:
        fenced = re.search(r"```json\s*(.*?)```", raw_output, flags=re.IGNORECASE | re.DOTALL)
        candidate = fenced.group(1).strip() if fenced else ""
        if not candidate:
            start = raw_output.find("{")
            end = raw_output.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("AI không trả về JSON")
            candidate = raw_output[start : end + 1]
        parsed = json.loads(candidate)
        if not isinstance(parsed, dict):
            raise ValueError("JSON đề xuất không phải là một đối tượng")
        return parsed

    @staticmethod
    def _proposal_fallback(alert: AlertDocument) -> AiAlertProposalResponse:
        return AiAlertProposalResponse(
            alert_id=str(alert.id),
            summary="Chưa đủ dữ liệu để đề xuất phương án lúc này.",
            actions=[],
        )

    async def generate_overdue_task_action_proposal(
        self,
        planning: OverdueTaskPlanningResponse,
        scope: ObjectId | None,
        actor_id: str | None = None,
    ) -> OverdueTaskPlanningResponse:
        """Explain backend-ranked options; the AI never calculates or executes them."""

        scope_label = "toàn công ty" if scope is None else "phòng ban của người dùng"
        option_data = [
            {
                "Mã phương án": option.option_id,
                "Loại phương án": option.type.value,
                "Nhân viên nhận việc": option.target_employee_name,
                "Hạn hoàn thành đề xuất": option.due_date.isoformat()
                if option.due_date
                else None,
                "Điểm phù hợp do backend tính": option.fit_score,
                "Độ tin cậy dữ liệu": option.confidence,
                "Bằng chứng": option.evidence,
            }
            for option in planning.options
        ]
        prompt = (
            f"{JSON_OBJECT_MODE_MARKER}\n"
            "Bạn là lớp diễn giải cho các phương án xử lý công việc quá hạn đã được backend "
            "tính toán. Không được tự tính lại điểm, thêm/bớt phương án, đổi mã phương án hoặc "
            "tự thực hiện cập nhật. Phạm vi dữ liệu là "
            f"{scope_label}.\n\n"
            "Các phương án hợp lệ do backend cung cấp:\n"
            f"{json.dumps(option_data, ensure_ascii=False, indent=2)}\n\n"
            "Chỉ trả về JSON hợp lệ, không markdown, theo cấu trúc: summary (chuỗi bắt buộc) "
            "và explanations (mảng). Mỗi explanation chỉ được dùng một Mã phương án đã cung "
            "cấp và có rationale ngắn bằng tiếng Việt. Nếu không thể diễn giải, trả summary "
            "thân thiện và explanations rỗng. Không đưa ra phương án mới."
        )

        try:
            parsed = self._extract_json(await self._collect_provider_output(prompt))
            validated = AiTaskPlanningExplanation.model_validate(parsed)
        except (ValidationError, ValueError, json.JSONDecodeError, TypeError):
            await self._audit(actor_id, scope, "overdue_task_explanation", prompt, "", "fallback")
            return planning
        except Exception:
            await self._audit(actor_id, scope, "overdue_task_explanation", prompt, "", "fallback")
            return planning

        summary = sanitize_ai_text(validated.summary)
        if not summary:
            return planning
        by_id = {option.option_id: option for option in planning.options}
        explained_options = planning.options.copy()
        for explanation in validated.explanations:
            option = by_id.get(explanation.option_id)
            if option is None:
                continue
            replacement = option.model_copy(update={"rationale": sanitize_ai_text(explanation.rationale)})
            explained_options[planning.options.index(option)] = replacement
        result = planning.model_copy(update={"summary": summary, "options": explained_options})

        await self._audit(
            actor_id,
            scope,
            "overdue_task_explanation",
            prompt,
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False),
            "success",
            {"option_count": len(result.options)},
        )
        return result

    async def generate_alert_action_proposal(
        self,
        alert: AlertDocument,
        scope: ObjectId | None,
        candidates: list[WorkloadCandidateResponse],
        actor_id: str | None = None,
    ) -> AiAlertProposalResponse:
        """Generate reviewable actions; the AI never executes an alert mutation."""

        cache_key = AiProposalCache.build_key(alert, candidates)
        cached = await self.proposal_cache.get(cache_key)
        if cached is not None:
            return cached

        scope_label = "toàn công ty" if scope is None else "phòng ban của người dùng"
        candidate_data = [
            {
                "Mã nhân viên để ánh xạ nội bộ": candidate.employee_id,
                "Tên nhân viên": candidate.employee_name,
                "Mã nhân viên hiển thị": candidate.employee_code,
                "Số công việc hoàn thành": candidate.tasks_completed,
                "Điểm chất lượng công việc": candidate.quality_score,
            }
            for candidate in candidates
        ]
        alert_data = {
            "Mã cảnh báo": str(alert.id),
            "Loại cảnh báo": alert.alert_type,
            "Mức độ cảnh báo": alert.severity.value,
            "Tên nhân viên liên quan": alert.employee_name,
            "Mã nhân viên liên quan": alert.employee_code,
            "Tiêu đề": alert.title,
            "Nội dung": alert.message,
            "Hành động gợi ý hiện có": alert.suggested_action,
            "Các ngày phát hiện": [item.isoformat() for item in alert.detected_dates],
        }
        prompt = (
            f"{JSON_OBJECT_MODE_MARKER}\n"
            "Bạn là trợ lý vận hành cho hệ thống quản lý hiệu suất. Hãy chỉ đề xuất, "
            "không tự áp dụng bất kỳ hành động nào. Phạm vi dữ liệu là "
            f"{scope_label}.\n\n"
            "Thông tin duy nhất của cảnh báo đang được xử lý:\n"
            f"{json.dumps(alert_data, ensure_ascii=False, indent=2)}\n\n"
            "Danh sách nhân viên thật có thể nhận bớt việc (chỉ được chọn đúng mã trong danh sách):\n"
            f"{json.dumps(candidate_data, ensure_ascii=False, indent=2)}\n\n"
            "Chỉ trả về một JSON hợp lệ, không markdown, không lời giải thích bên ngoài JSON, "
            "theo đúng cấu trúc sau: alert_id (chuỗi, bắt buộc), summary (chuỗi, bắt buộc), "
            "actions (mảng, bắt buộc). Mỗi action phải có rationale (chuỗi, bắt buộc), "
            "evidence (mảng tối đa 5 bằng chứng ngắn lấy từ dữ liệu đã cung cấp), priority "
            "(low/medium/high), data_as_of (thời điểm dữ liệu nếu biết), conditions (điều kiện "
            "áp dụng nếu có) và chỉ "
            "được là một trong hai loại:\n"
            '1) {"type":"resolve_alert","resolution_note":"...","rationale":"..."} '\
            "để ghi nhận xử lý cảnh báo; resolution_note bắt buộc.\n"
            '2) {"type":"apply_coordination","target_employee_id":"...",'
            '"tasks_to_transfer":1,"note":"...","rationale":"..."} '
            "để đề xuất chuyển việc; target_employee_id và tasks_to_transfer bắt buộc, "
            "tasks_to_transfer chỉ được là 1 hoặc 2, note có thể là null. Không được bịa hoặc "
            "chọn nhân viên ngoài danh sách đã cung cấp. Nếu chưa đủ dữ liệu, actions là mảng rỗng."
        )

        try:
            parsed = self._extract_json(await self._collect_provider_output(prompt))
            validated = AiAlertProposalResponse.model_validate(parsed)
        except (ValidationError, ValueError, json.JSONDecodeError, TypeError):
            await self._audit(actor_id, scope, "alert_proposal", prompt, "", "fallback")
            return self._proposal_fallback(alert)
        except Exception:
            await self._audit(actor_id, scope, "alert_proposal", prompt, "", "fallback")
            return self._proposal_fallback(alert)

        candidate_ids = {candidate.employee_id for candidate in candidates}
        filtered_actions: list[dict[str, Any]] = []
        for action in validated.actions:
            if isinstance(action, ApplyCoordinationProposal) and (
                action.target_employee_id not in candidate_ids
            ):
                continue
            action_data = action.model_dump()
            action_data["rationale"] = sanitize_ai_text(action.rationale)
            action_data["evidence"] = [sanitize_ai_text(item) for item in action.evidence]
            action_data["data_as_of"] = (
                sanitize_ai_text(action.data_as_of) if action.data_as_of else None
            )
            action_data["conditions"] = (
                sanitize_ai_text(action.conditions) if action.conditions else None
            )
            if isinstance(action, ResolveAlertProposal):
                action_data["resolution_note"] = sanitize_ai_text(action.resolution_note)
            else:
                action_data["note"] = sanitize_ai_text(action.note) if action.note else None
            filtered_actions.append(action_data)

        if not filtered_actions:
            await self._audit(actor_id, scope, "alert_proposal", prompt, "", "empty")
            return self._proposal_fallback(alert)

        summary = sanitize_ai_text(validated.summary)
        if not summary:
            await self._audit(actor_id, scope, "alert_proposal", prompt, "", "empty")
            return self._proposal_fallback(alert)
        try:
            result = AiAlertProposalResponse.model_validate(
                {
                    "alert_id": str(alert.id),
                    "summary": summary,
                    "actions": filtered_actions,
                }
            )
            await self.proposal_cache.set(cache_key, result)
            await self._audit(
                actor_id,
                scope,
                "alert_proposal",
                prompt,
                json.dumps(result.model_dump(mode="json"), ensure_ascii=False),
                "success",
                {"action_count": len(result.actions)},
            )
            return result
        except ValidationError:
            await self._audit(actor_id, scope, "alert_proposal", prompt, "", "fallback")
            return self._proposal_fallback(alert)

    @staticmethod
    def _leadership_proposal_fallback() -> AiLeadershipProposalResponse:
        return AiLeadershipProposalResponse(
            summary="Chưa đủ dữ liệu để đề xuất phương án cho Lãnh đạo lúc này.",
            actions=[],
        )

    async def generate_leadership_action_proposal(
        self,
        context: LeadershipAiContext,
        actor_id: str | None = None,
    ) -> AiLeadershipProposalResponse:
        """Generate reviewable Leadership drafts without executing any mutation."""

        prompt = (
            f"{JSON_OBJECT_MODE_MARKER}\n"
            "Bạn là trợ lý phân tích vận hành cho Lãnh đạo. Chỉ được đề xuất, không được "
            "phát hành chỉ thị, điều phối, thay đổi ngưỡng hoặc ghi dữ liệu. Chỉ sử dụng "
            "các số liệu tổng hợp bên dưới. Không được bịa phòng ban hoặc mã tham chiếu.\n\n"
            "Dữ liệu đã được backend kiểm tra quyền và rút gọn:\n"
            f"{json.dumps(context.to_prompt_data(include_internal_references=True), ensure_ascii=False, indent=2)}\n\n"
            "Chỉ trả về JSON hợp lệ, không markdown, theo cấu trúc: summary (chuỗi bắt buộc), "
            "key_findings (mảng), actions (mảng) và limitations (mảng). Mỗi finding phải có "
            "department_id, title, evidence tối đa 5 phần tử và severity low/medium/high. "
            "Mỗi action phải có rationale, evidence tối đa 5 phần tử và "
            "priority low/medium/high. Có đúng ba loại action hợp lệ:\n"
            '1) type="issue_department_directive": department_id là Mã phòng ban có trong dữ liệu, '
            "alert_type chỉ all/early_warning/overload, severity chỉ all/medium/high, note có thể null.\n"
            '2) type="cross_department_coordination": source_department_id và target_department_id '
            "phải khớp đúng một phương án trong Ứng viên điều phối liên phòng ban; action chỉ "
            "transfer_work/extend_deadline/reduce_scope/keep_and_extend; tasks_to_transfer chỉ 1 hoặc 2; note có thể null.\n"
            '3) type="propose_threshold_config": department_id có thể null hoặc phải có trong dữ liệu, '
            "consecutive_days chỉ từ 3 đến 7 và quality_drop_percent từ 1 đến 100. Đây chỉ là đề xuất, không tự thay đổi cấu hình.\n"
            '4) type="request_manager_explanation", "monitor_department" hoặc "request_manager_re_evaluation": '
            "department_id phải có trong dữ liệu; monitor_department có thể có monitoring_days từ 3 đến 30.\n"
            "Không tự điền điểm phù hợp; backend sẽ lấy điểm từ ứng viên thật. Không bịa mã phòng ban. "
            "Nếu chưa có cơ sở rõ ràng, trả actions rỗng."
        )
        try:
            parsed = self._extract_json(await self._collect_provider_output(prompt))
            validated = AiLeadershipProposalResponse.model_validate(parsed)
        except (ValidationError, ValueError, json.JSONDecodeError, TypeError):
            await self._audit(actor_id, None, "leadership_proposal", prompt, "", "fallback")
            return self._leadership_proposal_fallback()
        except Exception:
            await self._audit(actor_id, None, "leadership_proposal", prompt, "", "fallback")
            return self._leadership_proposal_fallback()

        allowed_department_ids = {
            item.department_id for item in context.departments
        } | {item.department_id for item in context.risks} | {
            item.department_id for item in context.overdue_work
        }
        allowed_department_ids |= {
            item.source_department_id for item in context.coordination_candidates
        }
        allowed_department_ids |= {
            item.target_department_id for item in context.coordination_candidates
        }
        department_names = {
            item.department_id: item.department_name for item in context.departments
        }
        department_names.update(
            {item.department_id: item.department_name for item in context.risks}
        )
        department_names.update(
            {item.department_id: item.department_name for item in context.overdue_work}
        )
        candidate_by_pair = {
            (item.source_department_id, item.target_department_id): item
            for item in context.coordination_candidates
        }
        filtered_actions: list[dict[str, Any]] = []
        for action in validated.actions:
            if isinstance(action, IssueDepartmentDirectiveProposal):
                if action.department_id not in allowed_department_ids:
                    continue
            elif isinstance(action, CrossDepartmentCoordinationProposal):
                candidate = candidate_by_pair.get(
                    (action.source_department_id, action.target_department_id)
                )
                if candidate is None:
                    continue
            elif isinstance(action, ThresholdConfigProposal):
                if action.department_id is not None and action.department_id not in allowed_department_ids:
                    continue
            elif isinstance(action, LeadershipFollowUpProposal):
                if action.department_id not in allowed_department_ids:
                    continue
            else:
                continue
            action_data = action.model_dump()
            action_data["rationale"] = sanitize_ai_text(action.rationale)
            if hasattr(action, "note"):
                action_data["note"] = sanitize_ai_text(action.note) if action.note else None
            for field_name in ("expected_impact", "risks"):
                field_value = getattr(action, field_name, None)
                if field_value:
                    action_data[field_name] = sanitize_ai_text(field_value)
            action_data["evidence"] = [sanitize_ai_text(item) for item in action.evidence]
            if not action_data["rationale"]:
                continue
            if isinstance(action, IssueDepartmentDirectiveProposal):
                action_data["department_name"] = department_names.get(action.department_id)
            elif isinstance(action, CrossDepartmentCoordinationProposal):
                candidate = candidate_by_pair[
                    (action.source_department_id, action.target_department_id)
                ]
                action_data.update(
                    {
                        "source_department_name": candidate.source_department_name,
                        "target_department_name": candidate.target_department_name,
                        "fit_score": candidate.fit_score,
                        "capacity_score": candidate.capacity_score,
                        "skill_fit_score": candidate.skill_fit_score,
                        "deadline_reliability_score": candidate.deadline_reliability_score,
                        "recent_quality_score": candidate.recent_quality_score,
                        "evidence": [sanitize_ai_text(item) for item in candidate.evidence],
                    }
                )
            elif isinstance(action, ThresholdConfigProposal):
                action_data["department_name"] = (
                    department_names.get(action.department_id) if action.department_id else "Toàn công ty"
                )
            elif isinstance(action, LeadershipFollowUpProposal):
                action_data["department_name"] = department_names.get(action.department_id)
            filtered_actions.append(action_data)

        summary = sanitize_ai_text(validated.summary)
        if not summary or not filtered_actions:
            await self._audit(actor_id, None, "leadership_proposal", prompt, "", "empty")
            return self._leadership_proposal_fallback()
        try:
            result = AiLeadershipProposalResponse.model_validate(
                {
                    "summary": summary,
                    "key_findings": [
                        {
                            **finding.model_dump(),
                            "title": sanitize_ai_text(finding.title),
                            "evidence": [sanitize_ai_text(item) for item in finding.evidence],
                        }
                        for finding in validated.key_findings
                        if finding.department_id in allowed_department_ids
                    ],
                    "actions": filtered_actions,
                    "limitations": [
                        sanitized
                        for item in validated.limitations
                        if (sanitized := sanitize_ai_text(item))
                    ],
                }
            )
        except ValidationError:
            await self._audit(actor_id, None, "leadership_proposal", prompt, "", "fallback")
            return self._leadership_proposal_fallback()
        await self._audit(
            actor_id,
            None,
            "leadership_proposal",
            prompt,
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False),
            "success",
            {"action_count": len(result.actions)},
        )
        return result
