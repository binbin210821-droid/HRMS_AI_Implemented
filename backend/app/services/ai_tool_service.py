from __future__ import annotations

import hashlib
import json
import re
from datetime import date as Date
from datetime import timedelta
from typing import Any, Literal

from bson import ObjectId
from pydantic import BaseModel

from app.ai.governance import AiAuditLogger
from app.ai.tool_factory import AiToolProviderFactory
from app.ai.tooling import (
    AiToolDefinition,
    AiToolError,
    AiToolRegistry,
    ToolCall,
    ToolExecutionContext,
)
from app.core.time import business_clock
from app.models.ai_tools import (
    ApplyCoordinationToolInput,
    ComparePerformancePeriodsToolInput,
    DepartmentPerformanceToolInput,
    DepartmentWeeklyEvaluationToolInput,
    EmployeePerformanceToolInput,
    ExplainAlertToolInput,
    LeadershipCrossDepartmentCandidatesToolInput,
    LeadershipDepartmentSummaryToolInput,
    LeadershipEvaluationToolInput,
    OpenAlertsToolInput,
    OverdueTasksToolInput,
    OverloadedEmployeesToolInput,
    PerformanceTrendToolInput,
    RebalanceCandidatesToolInput,
)
from app.models.user import CurrentUser, UserRole
from app.services.ai_data_tool_service import AiDataToolService
from app.services.coordination_service import CoordinationService

LEADERSHIP_DETAIL_POLICY_MESSAGE = (
    "Tôi có thể cung cấp số liệu tổng hợp theo phòng ban. "
    "Thông tin chi tiết từng nhân viên chỉ được hiển thị khi có nghiệp vụ được phép."
)

CONTEXT_REVALIDATION_MESSAGE = (
    "Ngữ cảnh dữ liệu trước đã hết hiệu lực. Vui lòng nêu lại khoảng thời gian "
    "cần xem để tôi kiểm tra lại."
)


class AiToolService:
    """Routes a model-selected read-only tool through existing business services."""

    @staticmethod
    def deterministic_tool_name(
        message: str, role: UserRole | None = None
    ) -> str | None:
        call = _infer_read_tool_call(message, role)
        return call.name if call is not None else None

    def __init__(
        self,
        coordination_service: CoordinationService,
        provider_factory: AiToolProviderFactory,
        registry: AiToolRegistry,
        audit_logger: AiAuditLogger | None = None,
        provider_name: str = "unknown",
        model: str = "unknown",
    ) -> None:
        self.coordination_service = coordination_service
        self.provider_factory = provider_factory
        self.registry = registry
        self.audit_logger = audit_logger
        self.provider_name = provider_name
        self.model = model

    async def preview_from_message(
        self, message: str, current_user: CurrentUser, scope: ObjectId | None
    ) -> tuple[
        Literal["executed", "approval_required", "no_tool_call", "unavailable"],
        str | None,
        dict[str, Any] | None,
        str,
    ]:
        if current_user.role != UserRole.MANAGER or scope is None:
            await self._audit(current_user.user_id, scope, message, "denied")
            return (
                "unavailable",
                None,
                None,
                "Chức năng này chỉ dành cho Quản lý trong phạm vi phòng ban của mình.",
            )

        return await self._read_data_from_message(message, current_user, scope)

    async def read_data_from_message(
        self,
        message: str,
        current_user: CurrentUser,
        scope: ObjectId | None,
        *,
        conversation_id: str | None = None,
        conversation_repository: Any | None = None,
        force_deterministic: bool = False,
    ) -> tuple[
        Literal["executed", "approval_required", "no_tool_call", "unavailable"],
        str | None,
        dict[str, Any] | None,
        str,
    ]:
        return await self._read_data_from_message(
            message,
            current_user,
            scope,
            conversation_id=conversation_id,
            conversation_repository=conversation_repository,
            force_deterministic=force_deterministic,
        )

    async def read_data_from_context(
        self,
        context: dict[str, Any],
        current_user: CurrentUser,
        scope: ObjectId | None,
        *,
        conversation_id: str | None = None,
        conversation_repository: Any | None = None,
    ) -> tuple[
        Literal[
            "executed",
            "approval_required",
            "no_tool_call",
            "unavailable",
            "context_invalid",
        ],
        str | None,
        dict[str, Any] | None,
        str,
    ]:
        tool_name = context.get("tool_name")
        arguments = context.get("arguments")
        if not isinstance(tool_name, str) or not isinstance(arguments, dict):
            return "no_tool_call", None, None, "Chưa có ngữ cảnh dữ liệu phù hợp để hỏi tiếp."
        try:
            definition = self.registry.definition(tool_name)
        except AiToolError as error:
            return "unavailable", tool_name, None, str(error)
        if not definition.read_only:
            return "unavailable", tool_name, None, "Ngữ cảnh trước đó không phải thao tác đọc dữ liệu."
        if _context_period_is_invalid(arguments):
            await self._audit(
                current_user.user_id,
                scope,
                "follow-up context",
                "context_invalid",
                tool_name,
            )
            return "context_invalid", tool_name, None, CONTEXT_REVALIDATION_MESSAGE
        normalized_call = _normalize_tool_call(
            ToolCall(tool_name, arguments), "", from_context=True
        )
        try:
            result = await self.registry.execute(
                normalized_call,
                ToolExecutionContext(
                    user_id=current_user.user_id,
                    role=current_user.role,
                    department_scope=scope,
                ),
            )
        except AiToolError as error:
            return "unavailable", tool_name, None, str(error)
        await self._save_conversation_context(
            conversation_id,
            conversation_repository,
            current_user,
            scope,
            normalized_call.name,
            normalized_call.arguments,
        )
        return result.status, result.tool_name, result.data, result.message

    async def _read_data_from_message(
        self,
        message: str,
        current_user: CurrentUser,
        scope: ObjectId | None,
        *,
        conversation_id: str | None = None,
        conversation_repository: Any | None = None,
        force_deterministic: bool = False,
    ) -> tuple[
        Literal["executed", "approval_required", "no_tool_call", "unavailable"],
        str | None,
        dict[str, Any] | None,
        str,
    ]:
        if current_user.role == UserRole.LEADERSHIP and _requests_restricted_employee_detail(message):
            await self._audit(
                current_user.user_id, scope, message, "policy_denied", None
            )
            return (
                "unavailable",
                None,
                None,
                LEADERSHIP_DETAIL_POLICY_MESSAGE,
            )
        definitions = [
            definition
            for definition in self.registry.definitions_for(current_user.role)
            if definition.read_only
        ]
        deterministic_call = _infer_read_tool_call(message, current_user.role)
        if deterministic_call is not None or force_deterministic:
            if deterministic_call is None:
                await self._audit(
                    current_user.user_id,
                    scope,
                    message,
                    "no_tool_call",
                )
                return "no_tool_call", None, None, "AI chưa xác định được thao tác đọc dữ liệu phù hợp."
            call = _normalize_tool_call(deterministic_call, message)
            route_status = "deterministic_recovery" if force_deterministic else "deterministic_route"
            await self._audit(current_user.user_id, scope, message, route_status, call.name)
            return await self._execute_read_call(
                call,
                message,
                current_user,
                scope,
                conversation_id,
                conversation_repository,
                recovery=force_deterministic,
            )

        prompt = (
            "Yêu cầu đọc dữ liệu của người dùng bằng tiếng Việt:\n"
            f"{message}\n\n"
            "Hãy chọn đúng một công cụ phù hợp nếu yêu cầu cần dữ liệu thực tế. Chỉ dùng đúng schema đã cung cấp. "
            "Không được suy đoán mã cảnh báo; nếu thiếu mã thì không gọi công cụ. "
            "Không được tự bịa date_from/date_to; nếu người dùng không nêu kỳ dữ liệu thì để hai trường này null. "
            "Không được điền tên phòng ban thay cho 'phòng tôi' hoặc 'phòng mình'. "
            "Không được suy đoán tên nhân viên; backend sẽ tự áp dụng phạm vi người dùng. "
            "Không được gọi công cụ thay đổi dữ liệu và không được tự viết truy vấn cơ sở dữ liệu."
        )
        try:
            call = await self.provider_factory.generate_tool_call(
                prompt, [definition.openai_schema for definition in definitions]
            )
        except Exception:
            await self._audit(current_user.user_id, scope, message, "provider_fallback")
            return "unavailable", None, None, "Trợ lý AI hiện chưa sẵn sàng, vui lòng thử lại sau."
        if call is None:
            await self._audit(current_user.user_id, scope, message, "no_tool_call")
            return "no_tool_call", None, None, "AI chưa xác định được thao tác đọc dữ liệu phù hợp."
        deterministic_call = _infer_read_tool_call(message, current_user.role)
        if deterministic_call is not None and call.name != deterministic_call.name:
            await self._audit(
                current_user.user_id,
                scope,
                message,
                "planner_tool_mismatch",
                call.name,
            )
        call = _normalize_tool_call(call, message)
        return await self._execute_read_call(
            call,
            message,
            current_user,
            scope,
            conversation_id,
            conversation_repository,
        )

    async def _execute_read_call(
        self,
        call: ToolCall,
        message: str,
        current_user: CurrentUser,
        scope: ObjectId | None,
        conversation_id: str | None,
        conversation_repository: Any | None,
        *,
        recovery: bool = False,
    ) -> tuple[
        Literal["executed", "approval_required", "no_tool_call", "unavailable"],
        str | None,
        dict[str, Any] | None,
        str,
    ]:
        await self._audit(current_user.user_id, scope, message, "tool_selected", call.name)
        try:
            result = await self.registry.execute(
                call,
                ToolExecutionContext(
                    user_id=current_user.user_id,
                    role=current_user.role,
                    department_scope=scope,
                ),
            )
        except AiToolError as error:
            await self._audit(current_user.user_id, scope, message, "rejected", call.name)
            return "unavailable", call.name, None, str(error)
        data_has_rows = bool(
            isinstance(result.data, dict)
            and result.data.get("co_du_lieu")
            and result.data.get("du_lieu")
        )
        await self._audit(
            current_user.user_id,
            scope,
            message,
            "tool_executed" if data_has_rows else ("no_data_after_recovery" if recovery else "no_data"),
            result.tool_name,
        )
        if result.status == "executed":
            await self._save_conversation_context(
                conversation_id,
                conversation_repository,
                current_user,
                scope,
                call.name,
                call.arguments,
            )
        return result.status, result.tool_name, result.data, result.message

    async def _save_conversation_context(
        self,
        conversation_id: str | None,
        conversation_repository: Any | None,
        current_user: CurrentUser,
        scope: ObjectId | None,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        if conversation_id is None or conversation_repository is None:
            return
        await conversation_repository.save_tool_context(
            conversation_id,
            current_user.user_id,
            scope,
            tool_name,
            arguments,
        )

    async def _audit(
        self,
        user_id: str,
        scope: ObjectId | None,
        message: str,
        status: str,
        tool_name: str | None = None,
    ) -> None:
        if self.audit_logger is None:
            return
        await self.audit_logger.record(
            actor_id=user_id,
            department_id=scope,
            provider=self.provider_name,
            model=self.model,
            request_type="tool_call",
            input_text=message,
            status=status,
            tool_name=tool_name,
        )


def build_tool_registry(
    coordination_service: CoordinationService,
    audit_logger: AiAuditLogger | None = None,
    data_service: AiDataToolService | None = None,
) -> AiToolRegistry:
    registry = AiToolRegistry(audit_writer=audit_logger or coordination_service.repository)

    async def get_candidates(
        arguments: RebalanceCandidatesToolInput,
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        alert, candidates = await coordination_service.get_rebalance_candidates_for_alert(
            arguments.alert_id, context.department_scope
        )
        return {
            "alert": {
                "alert_id": str(alert.id),
                "employee_name": alert.employee_name,
                "alert_type": alert.alert_type,
                "severity": alert.severity.value,
                "message": alert.message,
            },
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
        }

    registry.register(
        AiToolDefinition(
            name="get_rebalance_candidates",
            description=(
                "Đọc danh sách nhân viên cùng phòng ban có thể nhận bớt công việc "
                "cho một cảnh báo đang mở. Không áp dụng điều phối."
            ),
            input_model=RebalanceCandidatesToolInput,
            allowed_roles=frozenset({UserRole.MANAGER}),
            read_only=True,
            requires_human_approval=False,
            handler=get_candidates,
        )
    )

    if data_service is not None:
        async def get_department_performance(arguments, context):
            return await data_service.get_department_performance(arguments, context.department_scope)

        async def get_employee_performance(arguments, context):
            return await data_service.get_employee_performance(arguments, context.department_scope)

        async def get_performance_trend(arguments, context):
            return await data_service.get_performance_trend(arguments, context.department_scope)

        async def compare_performance_periods(arguments, context):
            return await data_service.get_compare_performance_periods(
                arguments, context.department_scope
            )

        async def explain_alert(arguments, context):
            return await data_service.explain_alert(arguments, context.department_scope)

        async def get_open_alerts(arguments, context):
            return await data_service.get_open_alerts(arguments, context.department_scope)

        async def get_overloaded_employees(arguments, context):
            return await data_service.get_overloaded_employees(arguments, context.department_scope)

        async def get_department_weekly_evaluation(arguments, context):
            return await data_service.get_department_weekly_evaluation(
                arguments, context.department_scope
            )

        async def get_overdue_tasks(arguments, context):
            return await data_service.get_overdue_tasks(arguments, context.department_scope)

        async def get_company_performance_summary(arguments, context):
            return await data_service.get_company_performance_summary(
                arguments, context.department_scope
            )

        async def compare_departments(arguments, context):
            return await data_service.compare_departments(arguments, context.department_scope)

        async def get_department_risk_summary(arguments, context):
            return await data_service.get_department_risk_summary(
                arguments, context.department_scope
            )

        async def get_manager_evaluations(arguments, context):
            return await data_service.get_manager_evaluations(
                arguments, context.department_scope
            )

        async def get_overdue_work_summary(arguments, context):
            return await data_service.get_overdue_work_summary(
                arguments, context.department_scope
            )

        async def get_cross_department_coordination_candidates(arguments, context):
            return await data_service.get_cross_department_coordination_candidates(
                arguments, context.department_scope
            )

        definitions: list[tuple[str, str, type[BaseModel], Any]] = [
            (
                "get_department_performance",
                "Đọc điểm hiệu suất và chất lượng tổng hợp của một hoặc các phòng ban trong khoảng ngày được yêu cầu.",
                DepartmentPerformanceToolInput,
                get_department_performance,
            ),
            (
                "get_employee_performance",
                "Đọc xu hướng hiệu suất của một nhân viên có tên trong phạm vi được cấp quyền.",
                EmployeePerformanceToolInput,
                get_employee_performance,
            ),
            (
                "get_performance_trend",
                "Đọc xu hướng điểm hiệu suất và điểm chất lượng theo ngày của phòng ban hoặc nhân viên trong phạm vi được cấp quyền.",
                PerformanceTrendToolInput,
                get_performance_trend,
            ),
            (
                "compare_performance_periods",
                "So sánh điểm hiệu suất và chất lượng giữa hai kỳ; phần trăm thay đổi do backend tính.",
                ComparePerformancePeriodsToolInput,
                compare_performance_periods,
            ),
            (
                "explain_alert",
                "Giải thích một cảnh báo đang mở bằng dữ liệu cảnh báo và chỉ số liên quan tối thiểu.",
                ExplainAlertToolInput,
                explain_alert,
            ),
            (
                "get_open_alerts",
                "Đọc các cảnh báo đang mở trong phạm vi được cấp quyền.",
                OpenAlertsToolInput,
                get_open_alerts,
            ),
            (
                "get_overloaded_employees",
                "Đọc danh sách ghi nhận nhân viên quá tải trong phạm vi được cấp quyền.",
                OverloadedEmployeesToolInput,
                get_overloaded_employees,
            ),
            (
                "get_department_weekly_evaluation",
                "Đọc đánh giá tổng hợp theo tuần của phòng ban, không đọc điểm chi tiết từng nhân viên.",
                DepartmentWeeklyEvaluationToolInput,
                get_department_weekly_evaluation,
            ),
            (
                "get_overdue_tasks",
                "Đọc các công việc đã quá hạn trong phạm vi được cấp quyền.",
                OverdueTasksToolInput,
                get_overdue_tasks,
            ),
        ]
        manager_only_tools = {
            "get_department_performance",
            "get_employee_performance",
            "get_performance_trend",
            "compare_performance_periods",
            "explain_alert",
            "get_open_alerts",
            "get_overloaded_employees",
            "get_overdue_tasks",
        }
        for name, description, input_model, handler in definitions:
            registry.register(
                AiToolDefinition(
                    name=name,
                    description=description,
                    input_model=input_model,
                    allowed_roles=frozenset(
                        {UserRole.MANAGER}
                        if name in manager_only_tools
                        else {UserRole.MANAGER, UserRole.LEADERSHIP}
                    ),
                    read_only=True,
                    requires_human_approval=False,
                    handler=handler,
                )
            )

        leadership_definitions: list[tuple[str, str, type[BaseModel], Any]] = [
            (
                "get_company_performance_summary",
                "Chỉ Lãnh đạo: đọc hiệu suất tổng hợp các phòng ban trong toàn công ty, không đọc chi tiết nhân viên.",
                LeadershipDepartmentSummaryToolInput,
                get_company_performance_summary,
            ),
            (
                "compare_departments",
                "Chỉ Lãnh đạo: so sánh các phòng ban bằng điểm hiệu suất và chất lượng tổng hợp do backend tính.",
                LeadershipDepartmentSummaryToolInput,
                compare_departments,
            ),
            (
                "get_department_risk_summary",
                "Chỉ Lãnh đạo: đọc tổng hợp cảnh báo, quá tải và công việc quá hạn theo phòng ban.",
                LeadershipDepartmentSummaryToolInput,
                get_department_risk_summary,
            ),
            (
                "get_manager_evaluations",
                "Chỉ Lãnh đạo: đọc các kỳ đánh giá tổng hợp của Quản lý/phòng ban.",
                LeadershipEvaluationToolInput,
                get_manager_evaluations,
            ),
            (
                "get_overdue_work_summary",
                "Chỉ Lãnh đạo: đọc số lượng và mức độ công việc quá hạn theo phòng ban, không đọc người phụ trách.",
                LeadershipDepartmentSummaryToolInput,
                get_overdue_work_summary,
            ),
            (
                "get_cross_department_coordination_candidates",
                "Chỉ Lãnh đạo: đọc các phương án hỗ trợ liên phòng ban ở cấp tổng hợp, gồm khả năng nhận thêm việc, mức khớp yêu cầu, khả năng đúng hạn và chất lượng gần đây. Không trả người cụ thể và không áp dụng điều phối.",
                LeadershipCrossDepartmentCandidatesToolInput,
                get_cross_department_coordination_candidates,
            ),
        ]
        for name, description, input_model, handler in leadership_definitions:
            registry.register(
                AiToolDefinition(
                    name=name,
                    description=description,
                    input_model=input_model,
                    allowed_roles=frozenset({UserRole.LEADERSHIP}),
                    read_only=True,
                    requires_human_approval=False,
                    handler=handler,
                )
            )

    # This is an explicit safety declaration, not an executable mutation. The
    # existing resolve/apply endpoints remain the only mutation paths.
    registry.register(
        AiToolDefinition(
            name="apply_coordination",
            description=(
                "Đề xuất điều phối công việc; luôn cần người dùng kiểm tra và áp dụng "
                "qua API nghiệp vụ hiện có. Công cụ AI không được tự thực thi."
            ),
            input_model=ApplyCoordinationToolInput,
            allowed_roles=frozenset({UserRole.MANAGER}),
            read_only=False,
            requires_human_approval=True,
            handler=None,
        )
    )
    return registry


def tool_input_fingerprint(message: str) -> str:
    return hashlib.sha256(json.dumps(message, ensure_ascii=False).encode()).hexdigest()


_DATE_AWARE_TOOLS = frozenset(
    {
        "get_department_performance",
        "get_employee_performance",
        "get_performance_trend",
        "compare_performance_periods",
        "get_overloaded_employees",
        "get_company_performance_summary",
        "compare_departments",
        "get_department_risk_summary",
        "get_manager_evaluations",
        "get_overdue_work_summary",
        "get_cross_department_coordination_candidates",
    }
)
_DEFAULT_SEVEN_DAY_TOOLS = frozenset(
    {
        "get_employee_performance",
        "get_performance_trend",
        "compare_performance_periods",
        "get_overloaded_employees",
    }
)
MAX_TOOL_RANGE_DAYS = 90


def _infer_read_tool_call(
    message: str, role: UserRole | None = None
) -> ToolCall | None:
    """Choose a bounded tool for high-confidence Vietnamese questions."""

    normalized = message.casefold()
    if role == UserRole.LEADERSHIP:
        if any(
            marker in normalized
            for marker in (
                "điều phối liên phòng ban",
                "hỗ trợ liên phòng ban",
                "phòng ban hỗ trợ",
                "nhận thêm việc",
            )
        ):
            return ToolCall(
                "get_cross_department_coordination_candidates",
                _with_source_department_reference(
                    _relative_date_arguments(normalized), message
                ),
            )
        if "đánh giá" in normalized and (
            "quản lý" in normalized or "phòng ban" in normalized
        ):
            return ToolCall(
                "get_manager_evaluations",
                _with_department_reference(_relative_date_arguments(normalized), message),
            )
        if "so sánh" in normalized or "so với" in normalized:
            return ToolCall(
                "compare_departments",
                _with_department_reference(_relative_date_arguments(normalized), message),
            )
        if "quá hạn" in normalized or "trễ hạn" in normalized or "overdue" in normalized:
            return ToolCall(
                "get_overdue_work_summary",
                _with_department_reference(_relative_date_arguments(normalized), message),
            )
        if any(marker in normalized for marker in ("cảnh báo", "quá tải", "rủi ro", "alert", "overload")):
            return ToolCall(
                "get_department_risk_summary",
                _with_department_reference(_relative_date_arguments(normalized), message),
            )
        if any(marker in normalized for marker in ("hiệu suất", "điểm", "phòng ban", "công ty")):
            return ToolCall(
                "get_company_performance_summary",
                _with_department_reference(_relative_date_arguments(normalized), message),
            )
    if (
        ("so sánh" in normalized or "so với" in normalized)
        and (
            "hiệu suất" in normalized
            or "điểm" in normalized
            or "tuần trước" in normalized
        )
    ) or (
        "tuần trước" in normalized
        and ("tốt hơn" in normalized or "tiến bộ" in normalized)
    ):
        arguments = _comparison_date_arguments(normalized)
        return ToolCall(
            "compare_performance_periods",
            _with_department_reference(arguments, message),
        )
    if "giải thích cảnh báo" in normalized:
        employee_name = _extract_employee_name(message)
        if employee_name:
            return ToolCall("explain_alert", {"employee_name": employee_name})
    if any(marker in normalized for marker in ("xu hướng", "diễn biến", "gần đây", "theo dõi")) and (
        "hiệu suất" in normalized or "điểm" in normalized
    ):
        employee_name = _extract_employee_name(message)
        arguments = _relative_date_arguments(normalized)
        if employee_name:
            arguments["employee_name"] = employee_name
        arguments = _with_department_reference(arguments, message)
        return ToolCall("get_performance_trend", arguments)
    if "cảnh báo" in normalized or "alert" in normalized:
        return ToolCall("get_open_alerts", {})
    if "quá tải" in normalized or "overload" in normalized:
        return ToolCall("get_overloaded_employees", _relative_date_arguments(normalized))
    if "quá hạn" in normalized or "trễ hạn" in normalized or "overdue" in normalized:
        return ToolCall("get_overdue_tasks", {})
    if "đánh giá" in normalized and "tuần" in normalized:
        return ToolCall("get_department_weekly_evaluation", {})
    if "hiệu suất" in normalized or "performance" in normalized:
        if "nhân viên" in normalized:
            employee_name = _extract_employee_name(message)
            if employee_name:
                return ToolCall("get_employee_performance", {"employee_name": employee_name})
        if "trong phòng" in normalized or "phòng tôi" in normalized or "phòng ban" in normalized:
            return ToolCall(
                "get_department_performance",
                _with_department_reference(_relative_date_arguments(normalized), message),
            )
        if "nhân viên" not in normalized:
            return ToolCall(
                "get_department_performance",
                _with_department_reference(_relative_date_arguments(normalized), message),
            )
    if "phòng tôi" in normalized and ("ai" in normalized or "chú ý" in normalized):
        return ToolCall("get_department_performance", {})
    return None


def _requests_restricted_employee_detail(message: str) -> bool:
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


def _comparison_date_arguments(message: str) -> dict[str, str]:
    period = _requested_period(message, comparison=True) or _default_period()
    start, end = _bounded_period(period)
    return {"date_from": start.isoformat(), "date_to": end.isoformat()}


def _with_department_reference(
    arguments: dict[str, Any], message: str
) -> dict[str, Any]:
    department_name = _extract_department_name(message)
    if department_name:
        arguments["department_name"] = department_name
    return arguments


def _with_source_department_reference(
    arguments: dict[str, Any], message: str
) -> dict[str, Any]:
    department_name = _extract_department_name(message)
    if department_name:
        arguments["source_department_name"] = department_name
    return arguments


def _normalize_tool_call(
    call: ToolCall, message: str, *, from_context: bool = False
) -> ToolCall:
    """Remove model-invented period/scope hints before registry validation."""

    arguments = dict(call.arguments)
    normalized = message.casefold()
    if call.name in _DATE_AWARE_TOOLS:
        requested_period = (
            _requested_period(normalized, comparison=call.name == "compare_performance_periods")
            if not from_context
            else _period_from_arguments(arguments)
        )
        if requested_period is None:
            arguments.pop("date_from", None)
            arguments.pop("date_to", None)
            if call.name in _DEFAULT_SEVEN_DAY_TOOLS:
                start, end = _bounded_period(_default_period())
                arguments["date_from"] = start.isoformat()
                arguments["date_to"] = end.isoformat()
        else:
            start, end = _bounded_period(requested_period)
            arguments["date_from"] = start.isoformat()
            arguments["date_to"] = end.isoformat()

    if "department_name" in arguments and not from_context:
        if not _has_explicit_department_reference(normalized):
            arguments.pop("department_name", None)
    return ToolCall(call.name, arguments)


def _default_period() -> tuple[Date, Date]:
    end = business_clock.today()
    return end - timedelta(days=6), end


def _bounded_period(period: tuple[Date, Date]) -> tuple[Date, Date]:
    today = business_clock.today()
    start, end = period
    if start > end or start > today:
        return _default_period()
    end = min(end, today)
    if (end - start).days + 1 > MAX_TOOL_RANGE_DAYS:
        start = end - timedelta(days=MAX_TOOL_RANGE_DAYS - 1)
    return start, end


def _requested_period(message: str, *, comparison: bool = False) -> tuple[Date, Date] | None:
    today = business_clock.today()
    if comparison and "tuần trước" in message:
        current_start = today - timedelta(days=today.weekday())
        return current_start, today
    if re.search(r"\b(?:7|bảy)\s*ngày\b", message):
        return today - timedelta(days=6), today
    if "hôm nay" in message:
        return today, today
    if "tuần này" in message:
        return today - timedelta(days=today.weekday()), today
    if "tuần trước" in message:
        end = today - timedelta(days=today.weekday() + 1)
        return end - timedelta(days=6), end
    if "tháng này" in message:
        return today.replace(day=1), today

    month_match = re.search(r"tháng\s+(\d{1,2})(?:\s+năm\s+(\d{4}))?", message)
    if month_match:
        month = int(month_match.group(1))
        year = int(month_match.group(2) or today.year)
        if 1 <= month <= 12:
            from calendar import monthrange

            return Date(year, month, 1), Date(year, month, monthrange(year, month)[1])

    year_match = re.search(r"năm\s+(\d{4})", message)
    if year_match:
        year = int(year_match.group(1))
        return Date(year, 1, 1), Date(year, 12, 31)

    dates: list[Date] = []
    for token in _DATE_TOKEN_RE.findall(message):
        parsed = _parse_date_token(token)
        if parsed is not None:
            dates.append(parsed)
    if dates:
        return min(dates), max(dates)
    return None


def _period_from_arguments(arguments: dict[str, Any]) -> tuple[Date, Date] | None:
    start = _coerce_date(arguments.get("date_from"))
    end = _coerce_date(arguments.get("date_to"))
    if start is None and end is None:
        return None
    resolved_start = start or end
    resolved_end = end or start
    if resolved_start is None or resolved_end is None:
        return None
    return resolved_start, resolved_end


def _context_period_is_invalid(arguments: dict[str, Any]) -> bool:
    raw_start = arguments.get("date_from")
    raw_end = arguments.get("date_to")
    if raw_start is None and raw_end is None:
        return False
    if raw_start is None or raw_end is None:
        return True
    start = _coerce_date(raw_start)
    end = _coerce_date(raw_end)
    if start is None or end is None:
        return True
    today = business_clock.today()
    return (
        start > end
        or start > today
        or end > today
        or (end - start).days + 1 > MAX_TOOL_RANGE_DAYS
    )


def _coerce_date(value: Any) -> Date | None:
    if isinstance(value, Date):
        return value
    if isinstance(value, str):
        try:
            return Date.fromisoformat(value)
        except ValueError:
            return None
    return None


_DATE_TOKEN_RE = re.compile(
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b"
)


def _parse_date_token(value: str) -> Date | None:
    try:
        parts = re.split(r"[-/]", value)
        if len(parts[0]) == 4:
            year, month, day = (int(part) for part in parts)
        else:
            day, month, year = (int(part) for part in parts)
        return Date(year, month, day)
    except (TypeError, ValueError):
        return None


def _has_explicit_department_reference(message: str) -> bool:
    generic = ("phòng tôi", "phòng mình", "phòng của tôi", "phòng này", "phòng ban")
    return "phòng" in message and not any(item in message for item in generic)


def _relative_date_arguments(message: str) -> dict[str, str]:
    today = business_clock.today()
    if re.search(r"\b(?:7|bảy)\s*ngày\b", message):
        start = today - timedelta(days=6)
        return {"date_from": start.isoformat(), "date_to": today.isoformat()}
    if "tuần này" in message:
        start = today - timedelta(days=today.weekday())
        return {"date_from": start.isoformat(), "date_to": today.isoformat()}
    if "tuần trước" in message:
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
        return {"date_from": start.isoformat(), "date_to": end.isoformat()}
    if "hôm nay" in message:
        return {"date_from": today.isoformat(), "date_to": today.isoformat()}
    if "tháng này" in message:
        start = today.replace(day=1)
        return {"date_from": start.isoformat(), "date_to": today.isoformat()}
    return {}


def _extract_employee_name(message: str) -> str | None:
    match = re.search(
        r"(?:của|nhân viên)\s+(.+?)(?=\s+(?:trong|về|gần đây|thế nào|ra sao|không)|[?.!,]|$)",
        message,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    name = " ".join(match.group(1).split()).strip()
    return name if 1 <= len(name) <= 120 else None


def _extract_department_name(message: str) -> str | None:
    match = re.search(r"\b(phòng(?:\s+ban)?\s+[^?.!,]+)", message, flags=re.IGNORECASE)
    if not match:
        return None
    name = " ".join(match.group(1).split()).strip()
    if name.casefold() in {"phòng tôi", "phòng mình", "phòng này"}:
        return None
    name = re.split(
        r"\s+(?:là|trong|về|có|thế nào|ra sao|tuần|hôm nay|gần đây|\d+\s*ngày)\b",
        name,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    return (
        name
        if name.casefold() not in {"phòng", "phòng ban", "phòng tôi", "phòng mình", "phòng này"}
        else None
    )


__all__ = ["AiToolService", "build_tool_registry", "tool_input_fingerprint"]
