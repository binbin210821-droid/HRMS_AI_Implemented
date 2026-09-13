import logging
from collections.abc import Callable
from typing import Any
from zoneinfo import ZoneInfo

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.config import get_settings
from app.core.pagination import Page
from app.core.time import BusinessClock
from app.events.event_bus import COORDINATION_APPLIED, EventBus, event_bus
from app.models.alert import AlertDocument
from app.models.coordination import (
    AcknowledgeDepartmentAlertDirectiveRequest,
    ApplyCoordinationRequest,
    CoordinationDirectiveDocument,
    CoordinationDirectiveResponse,
    CoordinationDirectiveStatus,
    CoordinationMode,
    CoordinationPlanDocument,
    CoordinationPlanResponse,
    CoordinationSuggestionResponse,
    DepartmentAlertDirectiveDocument,
    DepartmentAlertDirectiveResponse,
    DepartmentAlertDirectiveStatus,
    FulfillDirectiveRequest,
    IssueDepartmentAlertDirectiveRequest,
    ReviewDepartmentAlertDirectiveRequest,
    SubmitDepartmentAlertDirectiveRequest,
)
from app.models.overload import WorkloadCandidateResponse
from app.repositories.coordination_repository import CoordinationRepository
from app.repositories.department_repository import DepartmentRepository

logger = logging.getLogger(__name__)
DIRECTIVE_ALERT_TYPES = frozenset({"early_warning", "overload"})


class CoordinationService:
    """Applies a safe, same-department workload plan and records its audit trail."""

    def __init__(
        self,
        repository: CoordinationRepository,
        bus: EventBus = event_bus,
        department_repository: DepartmentRepository | None = None,
        clock: BusinessClock | None = None,
    ) -> None:
        self.repository = repository
        self.bus = bus
        self.department_repository = department_repository
        self._clock = clock or BusinessClock()
        self.business_timezone = ZoneInfo(get_settings().business_timezone)

    async def list_suggestions(
        self, scope: ObjectId | None
    ) -> list[CoordinationSuggestionResponse]:
        await self.repository.ensure_indexes()
        alerts = await self.repository.list_alerts(scope)
        return await self._suggestions_for_alerts(alerts)

    async def list_suggestions_page(
        self, scope: ObjectId | None, offset: int, limit: int
    ) -> Page[CoordinationSuggestionResponse]:
        await self.repository.ensure_indexes()
        page = await self.repository.list_alerts_page(scope, offset, limit)
        return Page(items=await self._suggestions_for_alerts(page.items), total=page.total)

    async def _suggestions_for_alerts(
        self, alerts: list[AlertDocument]
    ) -> list[CoordinationSuggestionResponse]:
        if not alerts:
            return []
        plans_by_alert = await self.repository.find_plans([alert.id for alert in alerts])
        candidates_by_group: dict[tuple[ObjectId, Any], list[WorkloadCandidateResponse]] = {}
        for alert in alerts:
            if alert.status.value != "open":
                continue
            group = (alert.department_id, self._alert_date(alert))
            if group not in candidates_by_group:
                candidates_by_group[group] = (
                    await self.repository.find_rebalance_candidates_for_group(*group)
                )
        responses: list[CoordinationSuggestionResponse] = []
        for alert in alerts:
            alert_date = self._alert_date(alert)
            candidates = list(candidates_by_group.get((alert.department_id, alert_date), []))
            candidates = [
                candidate
                for candidate in candidates
                if candidate.employee_id != str(alert.employee_id)
            ]
            responses.append(
                await self._suggestion_response(
                    alert, alert_date, candidates, plans_by_alert.get(alert.id)
                )
            )
        return responses

    async def apply(
        self,
        alert_id: str,
        scope: ObjectId | None,
        current_user_id: str,
        request: ApplyCoordinationRequest,
    ) -> CoordinationPlanResponse:
        alert = await self.get_open_alert(alert_id, scope)
        await self.repository.ensure_indexes()
        if await self.repository.find_plan(alert.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cảnh báo đã có phương án điều phối đang áp dụng",
            )
        if await self._find_directive_by_alert(alert.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cảnh báo đã có chỉ thị điều phối đang chờ hoặc đã hoàn tất",
            )

        alert_date = self._alert_date(alert)
        candidates = await self.repository.find_rebalance_candidates(
            alert.department_id, alert_date, alert.employee_id
        )
        target = self._select_candidate(candidates, request.target_employee_id)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Nhân viên nhận việc không còn phù hợp hoặc không thuộc phòng ban",
            )

        available_capacity = max(0, 4 - target.tasks_completed)
        transfer_count = request.tasks_to_transfer or min(2, available_capacity)
        if transfer_count < 1 or transfer_count > available_capacity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Số công việc điều phối vượt sức chứa an toàn của nhân viên nhận việc",
            )

        now = self._clock.now()
        plan_document: dict[str, Any] = {
            "_id": ObjectId(),
            "alert_id": alert.id,
            "department_id": alert.department_id,
            "target_department_id": alert.department_id,
            "source_employee_id": alert.employee_id,
            "target_employee_id": ObjectId(target.employee_id),
            "alert_date": alert_date,
            "tasks_to_transfer": transfer_count,
            "mode": (
                CoordinationMode.SUGGESTED.value
                if request.target_employee_id is None and request.tasks_to_transfer is None
                else CoordinationMode.CUSTOMIZED.value
            ),
            "note": request.note.strip() if request.note and request.note.strip() else None,
            "created_by": self._parse_object_id(current_user_id, "Mã người thực hiện"),
            "created_at": now,
            "updated_at": now,
        }
        async def persist(session: Any | None) -> CoordinationPlanDocument:
            plan = await self._repository_call("insert_plan", plan_document, session=session)
            resolution_note = (
                f"Đã áp dụng điều phối: chuyển {transfer_count} công việc cho "
                f"{target.employee_name}."
            )
            if request.note and request.note.strip():
                resolution_note = f"{resolution_note} Ghi chú: {request.note.strip()}"
            await self._repository_call(
                "insert_audit_log",
                {
                    "action": "workload_coordination_applied",
                    "actor_id": plan.created_by,
                    "alert_id": plan.alert_id,
                    "department_id": plan.department_id,
                    "source_employee_id": plan.source_employee_id,
                    "target_employee_id": plan.target_employee_id,
                    "tasks_to_transfer": plan.tasks_to_transfer,
                    "mode": plan.mode.value,
                    "created_at": now,
                },
                session=session,
            )
            resolved_alert = await self._repository_call(
                "resolve_alert_for_coordination",
                alert.id,
                plan.created_by,
                resolution_note,
                now,
                session=session,
            )
            if resolved_alert is None or resolved_alert.status.value != "resolved":
                raise PyMongoError("Không thể cập nhật trạng thái cảnh báo sau khi điều phối")
            return plan

        try:
            plan = await self._run_write_transaction(persist)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cảnh báo đã có phương án điều phối đang áp dụng",
            ) from error
        except PyMongoError:
            logger.exception("Không thể ghi phương án điều phối và audit log")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chưa thể lưu phương án điều phối, vui lòng thử lại",
            ) from None

        # Internal audit/observability signal only; there is intentionally no
        # runtime subscriber. Clients receive the alert/directive Change Stream
        # updates produced by this request at the same time.
        await self.bus.publish(COORDINATION_APPLIED, plan)
        return await self._plan_response(plan)

    async def get_open_alert(self, alert_id: str, scope: ObjectId | None) -> AlertDocument:
        """Return one open alert after applying the same scope checks as mutations."""

        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lãnh đạo không trực tiếp xử lý cảnh báo của Manager",
            )
        object_id = self._parse_object_id(alert_id, "Mã cảnh báo")
        alert = await self.repository.find_alert(object_id)
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cảnh báo"
            )
        if alert.department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xử lý cảnh báo ngoài phòng ban",
            )
        if alert.status.value != "open":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cảnh báo đã được xử lý, không thể tạo đề xuất mới",
            )
        return alert

    async def get_rebalance_candidates_for_alert(
        self, alert_id: str, scope: ObjectId | None
    ) -> tuple[AlertDocument, list[WorkloadCandidateResponse]]:
        alert = await self.get_open_alert(alert_id, scope)
        candidates = await self.repository.find_rebalance_candidates(
            alert.department_id, self._alert_date(alert), alert.employee_id
        )
        return alert, candidates

    async def list_directives(
        self, scope: ObjectId | None, directive_status: str | None = None
    ) -> list[CoordinationDirectiveResponse]:
        await self.repository.ensure_indexes()
        directives = await self.repository.list_directives(scope, directive_status)
        return [await self._directive_response(directive) for directive in directives]

    async def list_directives_page(
        self,
        scope: ObjectId | None,
        directive_status: str | None,
        offset: int,
        limit: int,
    ) -> Page[CoordinationDirectiveResponse]:
        await self.repository.ensure_indexes()
        page = await self.repository.list_directives_page(
            scope, directive_status, offset, limit
        )
        return Page(
            items=[await self._directive_response(directive) for directive in page.items],
            total=page.total,
        )

    async def list_directive_candidates(
        self, directive_id: str, scope: ObjectId | None
    ) -> list[WorkloadCandidateResponse]:
        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lãnh đạo không trực tiếp tiếp nhận chỉ thị điều phối",
            )
        object_id = self._parse_object_id(directive_id, "Mã chỉ thị điều phối")
        directive = await self.repository.find_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị điều phối"
            )
        if directive.target_department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem ứng viên của phòng ban khác",
            )
        if directive.status != CoordinationDirectiveStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị điều phối đã được tiếp nhận",
            )
        alert = await self.repository.find_alert(directive.alert_id)
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cảnh báo liên quan"
            )
        return await self.repository.find_rebalance_candidates(
            scope, self._alert_date(alert), alert.employee_id
        )

    async def list_directive_candidates_page(
        self, directive_id: str, scope: ObjectId | None, offset: int, limit: int
    ) -> Page[WorkloadCandidateResponse]:
        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lãnh đạo không trực tiếp tiếp nhận chỉ thị điều phối",
            )
        object_id = self._parse_object_id(directive_id, "Mã chỉ thị điều phối")
        directive = await self.repository.find_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị điều phối"
            )
        if directive.target_department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xem ứng viên của phòng ban khác",
            )
        if directive.status != CoordinationDirectiveStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị điều phối đã được tiếp nhận",
            )
        alert = await self.repository.find_alert(directive.alert_id)
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cảnh báo liên quan"
            )
        return await self.repository.find_rebalance_candidates_page(
            scope, self._alert_date(alert), alert.employee_id, offset, limit
        )

    async def fulfill_directive(
        self,
        directive_id: str,
        scope: ObjectId | None,
        current_user_id: str,
        request: FulfillDirectiveRequest,
    ) -> CoordinationPlanResponse:
        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lãnh đạo không trực tiếp tiếp nhận chỉ thị điều phối",
            )
        object_id = self._parse_object_id(directive_id, "Mã chỉ thị điều phối")
        await self.repository.ensure_indexes()
        directive = await self.repository.find_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị điều phối"
            )
        if directive.target_department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền tiếp nhận chỉ thị của phòng ban khác",
            )
        if directive.status != CoordinationDirectiveStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị điều phối đã được tiếp nhận",
            )

        alert = await self.repository.find_alert(directive.alert_id)
        if alert is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cảnh báo liên quan"
            )
        if alert.status.value != "open":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cảnh báo liên quan đã được xử lý, không thể tiếp nhận chỉ thị",
            )
        candidates = await self.repository.find_rebalance_candidates(
            scope, self._alert_date(alert), alert.employee_id
        )
        target = self._select_candidate(candidates, request.target_employee_id)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Nhân viên nhận việc không còn phù hợp hoặc không thuộc phòng ban đích",
            )

        available_capacity = max(0, 4 - target.tasks_completed)
        transfer_count = request.tasks_to_transfer or min(2, available_capacity)
        if transfer_count < 1 or transfer_count > available_capacity:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Số công việc tiếp nhận vượt sức chứa an toàn của nhân viên",
            )

        now = self._clock.now()
        manager_id = self._parse_object_id(current_user_id, "Mã người tiếp nhận")
        plan_document: dict[str, Any] = {
            "_id": ObjectId(),
            "alert_id": alert.id,
            "department_id": directive.source_department_id,
            "target_department_id": scope,
            "source_employee_id": alert.employee_id,
            "target_employee_id": ObjectId(target.employee_id),
            "alert_date": self._alert_date(alert),
            "tasks_to_transfer": transfer_count,
            "mode": CoordinationMode.CUSTOMIZED.value,
            "note": directive.note,
            "created_by": manager_id,
            "created_at": now,
            "updated_at": now,
        }
        async def persist(session: Any | None) -> CoordinationPlanDocument:
            plan = await self._repository_call("insert_plan", plan_document, session=session)
            resolution_note = (
                f"Đã tiếp nhận chỉ thị điều phối: chuyển {transfer_count} công việc cho "
                f"{target.employee_name}."
            )
            await self._repository_call(
                "insert_audit_log",
                {
                    "action": "cross_department_coordination_fulfilled",
                    "actor_id": plan.created_by,
                    "alert_id": plan.alert_id,
                    "department_id": plan.department_id,
                    "target_department_id": plan.target_department_id,
                    "source_employee_id": plan.source_employee_id,
                    "target_employee_id": plan.target_employee_id,
                    "tasks_to_transfer": plan.tasks_to_transfer,
                    "mode": plan.mode.value,
                    "created_at": now,
                },
                session=session,
            )
            resolved_alert = await self._repository_call(
                "resolve_alert_for_coordination",
                alert.id,
                plan.created_by,
                resolution_note,
                now,
                session=session,
            )
            if resolved_alert is None or resolved_alert.status.value != "resolved":
                raise PyMongoError(
                    "Không thể cập nhật trạng thái cảnh báo sau khi tiếp nhận chỉ thị"
                )
            fulfilled = await self._repository_call(
                "mark_directive_fulfilled",
                directive.id,
                plan.id,
                manager_id,
                now,
                session=session,
            )
            if fulfilled is None or fulfilled.status != CoordinationDirectiveStatus.FULFILLED:
                raise PyMongoError("Không thể cập nhật trạng thái chỉ thị điều phối")
            return plan

        try:
            plan = await self._run_write_transaction(persist)
        except DuplicateKeyError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị hoặc cảnh báo đã có phương án điều phối",
            ) from error
        except PyMongoError:
            logger.exception("Không thể ghi nhận việc tiếp nhận chỉ thị điều phối")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Chưa thể lưu việc tiếp nhận chỉ thị, vui lòng thử lại",
            ) from None

        # Internal audit/observability signal only; there is intentionally no
        # runtime subscriber. Clients receive the alert/directive Change Stream
        # updates produced by this request at the same time.
        await self.bus.publish(COORDINATION_APPLIED, plan)
        return await self._plan_response(plan)

    async def _run_write_transaction(self, operation: Callable[[Any | None], Any]) -> Any:
        """Run a coordination write set atomically when Mongo supports sessions.

        Test repositories without a Mongo client keep the same service contract and
        execute the operation directly. Production repositories always expose the
        Motor client, so plan, audit, alert and directive state commit together.
        """

        client = getattr(self.repository, "client", None)
        if client is None:
            return await operation(None)
        async with await client.start_session() as session:
            async with session.start_transaction():
                return await operation(session)

    async def _repository_call(self, method_name: str, *args: Any, session: Any | None) -> Any:
        method = getattr(self.repository, method_name)
        if session is None:
            return await method(*args)
        return await method(*args, session=session)

    async def list_department_directives(
        self, scope: ObjectId | None, directive_status: str | None = None
    ) -> list[DepartmentAlertDirectiveResponse]:
        await self.repository.ensure_indexes()
        directives = await self.repository.list_department_directives(scope, directive_status)
        return [await self._department_directive_response(directive) for directive in directives]

    async def list_department_directives_page(
        self,
        scope: ObjectId | None,
        directive_status: str | None,
        offset: int,
        limit: int,
    ) -> Page[DepartmentAlertDirectiveResponse]:
        await self.repository.ensure_indexes()
        page = await self.repository.list_department_directives_page(
            scope, directive_status, offset, limit
        )
        return Page(
            items=[
                await self._department_directive_response(directive)
                for directive in page.items
            ],
            total=page.total,
        )

    async def issue_department_directive(
        self,
        department_id: str,
        current_user_id: str,
        request: IssueDepartmentAlertDirectiveRequest,
    ) -> DepartmentAlertDirectiveResponse:
        department_object_id = self._parse_object_id(department_id, "Mã phòng ban")
        await self.repository.ensure_indexes()
        department = await self.repository.find_department(department_object_id)
        if department is None or not department.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Không tìm thấy phòng ban đang hoạt động",
            )
        manager = await self.repository.find_active_manager_by_department(department_object_id)
        if manager is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phòng ban chưa có Quản lý đang hoạt động",
            )
        pending_directives = await self._list_pending_department_directives(department_object_id)
        if any(
            self._directive_filters_overlap(
                directive.selected_alert_type,
                directive.selected_severity,
                request.alert_type,
                request.severity,
            )
            for directive in pending_directives
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phòng ban đã có chỉ thị đang chờ cho nhóm cảnh báo này",
            )

        matching_alerts = await self.repository.list_alerts_by_department(
            department_object_id,
            status="open",
            alert_type=None if request.alert_type == "all" else request.alert_type,
            severity=None if request.severity == "all" else request.severity,
        )
        matching_alerts = [
            alert for alert in matching_alerts if alert.alert_type in DIRECTIVE_ALERT_TYPES
        ]
        existing_directives = await self.repository.list_department_directives(department_object_id)
        directed_alert_ids = {
            alert_id for directive in existing_directives for alert_id in directive.alert_ids
        }
        selected_alerts = [alert for alert in matching_alerts if alert.id not in directed_alert_ids]
        if not selected_alerts:
            if matching_alerts:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Các cảnh báo phù hợp đã được gửi chỉ thị trước đó",
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Không có cảnh báo đang mở phù hợp để phát hành chỉ thị",
            )
        all_alerts = [
            alert
            for alert in await self.repository.list_alerts_by_department(department_object_id)
            if alert.alert_type in DIRECTIVE_ALERT_TYPES
        ]
        now = self._clock.now()
        document: dict[str, Any] = {
            "_id": ObjectId(),
            "department_id": department_object_id,
            "target_department_id": department_object_id,
            "target_manager_id": manager.id,
            "alert_ids": [alert.id for alert in selected_alerts],
            "selected_alert_type": request.alert_type,
            "selected_severity": request.severity,
            "selected_alert_count": len(selected_alerts),
            "selected_open_count": len(selected_alerts),
            "total_count": len(all_alerts),
            "open_count": sum(alert.status.value == "open" for alert in all_alerts),
            "resolved_count": sum(alert.status.value == "resolved" for alert in all_alerts),
            "early_warning_count": sum(alert.alert_type == "early_warning" for alert in all_alerts),
            "overload_count": sum(alert.alert_type == "overload" for alert in all_alerts),
            "high_count": sum(alert.severity.value == "high" for alert in all_alerts),
            "note": request.note.strip() if request.note and request.note.strip() else None,
            "status": DepartmentAlertDirectiveStatus.PENDING.value,
            "issued_by": self._parse_object_id(current_user_id, "Mã người phát hành"),
            "issued_at": now,
        }
        try:
            directive = await self.repository.insert_department_directive(document)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phòng ban đã có chỉ thị đang chờ cho nhóm cảnh báo này",
            ) from None

        await self.repository.insert_audit_log(
            {
                "action": "department_alert_directive_issued",
                "actor_id": directive.issued_by,
                "directive_id": directive.id,
                "department_id": directive.department_id,
                "target_department_id": directive.target_department_id,
                "alert_ids": directive.alert_ids,
                "selected_alert_count": directive.selected_alert_count,
                "created_at": now,
            }
        )
        return await self._department_directive_response(directive)

    async def acknowledge_department_directive(
        self,
        directive_id: str,
        scope: ObjectId | None,
        current_user_id: str,
        request: AcknowledgeDepartmentAlertDirectiveRequest,
    ) -> DepartmentAlertDirectiveResponse:
        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lãnh đạo không trực tiếp xác nhận chỉ thị cấp phòng ban",
            )
        object_id = self._parse_object_id(directive_id, "Mã chỉ thị phòng ban")
        await self.repository.ensure_indexes()
        directive = await self.repository.find_department_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị phòng ban"
            )
        if directive.target_department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền xác nhận chỉ thị của phòng ban khác",
            )
        if directive.status != DepartmentAlertDirectiveStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị phòng ban đã được xác nhận",
            )
        now = self._clock.now()
        acknowledged_by = self._parse_object_id(current_user_id, "Mã người xác nhận")
        note = request.note.strip() if request.note and request.note.strip() else None
        if request.commitment_date < now.astimezone(self.business_timezone).date():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ngày cam kết không được nằm trong quá khứ",
            )
        acknowledged = await self.repository.acknowledge_department_directive(
            directive.id, acknowledged_by, now, note, request.commitment_date
        )
        if (
            acknowledged is None
            or acknowledged.status != DepartmentAlertDirectiveStatus.ACKNOWLEDGED
        ):
            raise PyMongoError("Không thể cập nhật trạng thái chỉ thị phòng ban")
        await self.repository.insert_audit_log(
            {
                "action": "department_alert_directive_acknowledged",
                "actor_id": acknowledged_by,
                "directive_id": acknowledged.id,
                "department_id": acknowledged.department_id,
                "target_department_id": acknowledged.target_department_id,
                "acknowledgement_note": note,
                "commitment_date": request.commitment_date,
                "created_at": now,
            }
        )
        return await self._department_directive_response(acknowledged)

    async def submit_department_directive(
        self,
        directive_id: str,
        scope: ObjectId | None,
        submitted_by: str,
        request: SubmitDepartmentAlertDirectiveRequest,
    ) -> DepartmentAlertDirectiveResponse:
        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lãnh đạo không trực tiếp gửi nghiệm thu chỉ thị cảnh báo",
            )
        object_id = self._parse_object_id(directive_id, "Mã chỉ thị phòng ban")
        directive = await self.repository.find_department_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị phòng ban"
            )
        if directive.target_department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền gửi nghiệm thu chỉ thị của phòng ban khác",
            )
        if directive.status not in {
            DepartmentAlertDirectiveStatus.ACKNOWLEDGED,
            DepartmentAlertDirectiveStatus.NEEDS_REVISION,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị phòng ban chưa ở trạng thái có thể gửi nghiệm thu",
            )
        progress = await self._department_directive_progress(directive)
        if progress[2] < 100:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị chỉ được gửi nghiệm thu khi tất cả cảnh báo đã được xử lý",
            )
        now = self._clock.now()
        user_id = self._parse_object_id(submitted_by, "Mã người gửi nghiệm thu")
        updated = await self.repository.transition_department_directive(
            directive.id,
            [
                DepartmentAlertDirectiveStatus.ACKNOWLEDGED.value,
                DepartmentAlertDirectiveStatus.NEEDS_REVISION.value,
            ],
            {
                "status": DepartmentAlertDirectiveStatus.SUBMITTED.value,
                "completion_note": self._clean_note(request.completion_note),
                "submitted_by": user_id,
                "submitted_at": now,
            },
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị phòng ban vừa được cập nhật, vui lòng tải lại",
            )
        await self.repository.insert_audit_log(
            {
                "action": "department_alert_directive_submitted",
                "actor_id": user_id,
                "directive_id": updated.id,
                "department_id": updated.target_department_id,
                "completion_note": updated.completion_note,
                "created_at": now,
            }
        )
        return await self._department_directive_response(updated)

    async def accept_department_directive(
        self,
        directive_id: str,
        accepted_by: str,
        request: ReviewDepartmentAlertDirectiveRequest,
    ) -> DepartmentAlertDirectiveResponse:
        object_id = self._parse_object_id(directive_id, "Mã chỉ thị phòng ban")
        directive = await self.repository.find_department_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị phòng ban"
            )
        if directive.status != DepartmentAlertDirectiveStatus.SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị phòng ban chưa được gửi nghiệm thu",
            )
        if (await self._department_directive_progress(directive))[2] < 100:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cảnh báo trong chỉ thị chưa được xử lý đủ 100%",
            )
        now = self._clock.now()
        user_id = self._parse_object_id(accepted_by, "Mã người nghiệm thu")
        updated = await self.repository.transition_department_directive(
            directive.id,
            [DepartmentAlertDirectiveStatus.SUBMITTED.value],
            {
                "status": DepartmentAlertDirectiveStatus.ACCEPTED.value,
                "accepted_by": user_id,
                "accepted_at": now,
                "acceptance_note": self._clean_note(request.note),
            },
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị phòng ban vừa được người khác nghiệm thu",
            )
        await self.repository.insert_audit_log(
            {
                "action": "department_alert_directive_accepted",
                "actor_id": user_id,
                "directive_id": updated.id,
                "department_id": updated.target_department_id,
                "acceptance_note": updated.acceptance_note,
                "created_at": now,
            }
        )
        return await self._department_directive_response(updated)

    async def request_department_directive_revision(
        self,
        directive_id: str,
        requested_by: str,
        request: ReviewDepartmentAlertDirectiveRequest,
    ) -> DepartmentAlertDirectiveResponse:
        note = self._clean_note(request.note)
        if not note:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vui lòng nhập lý do yêu cầu xử lý lại",
            )
        object_id = self._parse_object_id(directive_id, "Mã chỉ thị phòng ban")
        directive = await self.repository.find_department_directive(object_id)
        if directive is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy chỉ thị phòng ban"
            )
        if directive.status != DepartmentAlertDirectiveStatus.SUBMITTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị phòng ban chưa được gửi nghiệm thu",
            )
        now = self._clock.now()
        user_id = self._parse_object_id(requested_by, "Mã người yêu cầu xử lý lại")
        updated = await self.repository.transition_department_directive(
            directive.id,
            [DepartmentAlertDirectiveStatus.SUBMITTED.value],
            {
                "status": DepartmentAlertDirectiveStatus.NEEDS_REVISION.value,
                "revision_requested_by": user_id,
                "revision_requested_at": now,
                "revision_note": note,
            },
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Chỉ thị phòng ban vừa được cập nhật, vui lòng tải lại",
            )
        await self.repository.insert_audit_log(
            {
                "action": "department_alert_directive_revision_requested",
                "actor_id": user_id,
                "directive_id": updated.id,
                "department_id": updated.target_department_id,
                "revision_note": note,
                "created_at": now,
            }
        )
        return await self._department_directive_response(updated)

    async def _department_directive_response(
        self, directive: DepartmentAlertDirectiveDocument
    ) -> DepartmentAlertDirectiveResponse:
        department_name = "Phòng ban chưa xác định"
        manager_name = None
        acknowledged_by_name = None
        department = await self.repository.find_department(directive.department_id)
        if department is not None:
            department_name = department.name
        manager = await self.repository.find_active_manager_by_department(
            directive.target_department_id
        )
        if manager is not None and manager.id == directive.target_manager_id:
            manager_name = manager.full_name
        if directive.acknowledged_by:
            find_user = getattr(self.repository, "find_user", None)
            if find_user is not None:
                user = await find_user(directive.acknowledged_by)
                if user is not None:
                    acknowledged_by_name = user.full_name
        completed_count, total_count, progress_percent = await self._department_directive_progress(
            directive
        )
        people = {"acknowledged_by": acknowledged_by_name}
        for field in ("submitted_by", "accepted_by", "revision_requested_by"):
            user_id = getattr(directive, field)
            if user_id:
                find_user = getattr(self.repository, "find_user", None)
                if find_user is not None:
                    user = await find_user(user_id)
                    people[field] = user.full_name if user else None
        return DepartmentAlertDirectiveResponse(
            id=str(directive.id),
            department_id=str(directive.department_id),
            department_name=department_name,
            target_department_id=str(directive.target_department_id),
            target_manager_id=str(directive.target_manager_id),
            target_manager_name=manager_name,
            alert_ids=[str(alert_id) for alert_id in directive.alert_ids],
            selected_alert_type=directive.selected_alert_type,
            selected_severity=directive.selected_severity,
            selected_alert_count=directive.selected_alert_count,
            selected_open_count=directive.selected_open_count,
            total_count=directive.total_count,
            open_count=directive.open_count,
            resolved_count=directive.resolved_count,
            early_warning_count=directive.early_warning_count,
            overload_count=directive.overload_count,
            high_count=directive.high_count,
            note=directive.note,
            status=directive.status,
            issued_by=str(directive.issued_by),
            issued_at=directive.issued_at,
            acknowledged_by=(str(directive.acknowledged_by) if directive.acknowledged_by else None),
            acknowledged_by_name=acknowledged_by_name,
            acknowledged_at=directive.acknowledged_at,
            acknowledgement_note=directive.acknowledgement_note,
            commitment_date=directive.commitment_date,
            completion_note=directive.completion_note,
            submitted_by=str(directive.submitted_by) if directive.submitted_by else None,
            submitted_by_name=people.get("submitted_by"),
            submitted_at=directive.submitted_at,
            accepted_by=str(directive.accepted_by) if directive.accepted_by else None,
            accepted_by_name=people.get("accepted_by"),
            accepted_at=directive.accepted_at,
            acceptance_note=directive.acceptance_note,
            revision_requested_by=(
                str(directive.revision_requested_by) if directive.revision_requested_by else None
            ),
            revision_requested_by_name=people.get("revision_requested_by"),
            revision_requested_at=directive.revision_requested_at,
            revision_note=directive.revision_note,
            completed_item_count=completed_count,
            total_item_count=total_count,
            progress_percent=progress_percent,
        )

    async def _department_directive_progress(
        self, directive: DepartmentAlertDirectiveDocument
    ) -> tuple[int, int, int]:
        find_alerts = getattr(self.repository, "find_alerts_by_ids", None)
        if find_alerts is None:
            total = directive.selected_alert_count
            return 0, total, 0
        alerts = await find_alerts(directive.alert_ids)
        total = len(directive.alert_ids)
        resolved = sum(
            getattr(alert.status, "value", alert.status) == "resolved" for alert in alerts
        )
        return resolved, total, round(resolved * 100 / total) if total else 0

    @staticmethod
    def _clean_note(value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    async def _list_pending_department_directives(
        self, department_id: ObjectId
    ) -> list[DepartmentAlertDirectiveDocument]:
        list_pending = getattr(self.repository, "list_pending_department_directives", None)
        if list_pending is not None:
            return await list_pending(department_id)
        pending = await self.repository.find_pending_department_directive(department_id)
        return [pending] if pending is not None else []

    @staticmethod
    def _directive_filters_overlap(
        left_alert_type: str,
        left_severity: str,
        right_alert_type: str,
        right_severity: str,
    ) -> bool:
        type_overlaps = (
            left_alert_type == "all"
            or right_alert_type == "all"
            or left_alert_type == right_alert_type
        )
        severity_overlaps = (
            left_severity == "all" or right_severity == "all" or left_severity == right_severity
        )
        return type_overlaps and severity_overlaps

    async def _find_directive_by_alert(
        self, alert_id: ObjectId
    ) -> CoordinationDirectiveDocument | None:
        finder = getattr(self.repository, "find_directive_by_alert", None)
        if finder is None:
            return None
        return await finder(alert_id)

    async def _directive_response(
        self, directive: CoordinationDirectiveDocument
    ) -> CoordinationDirectiveResponse:
        source_name = None
        target_name = "Phòng ban chưa xác định"
        if self.department_repository is not None:
            source = await self.department_repository.find_by_id(directive.source_department_id)
            if source is not None:
                source_name = source.name
            target = await self.department_repository.find_by_id(directive.target_department_id)
            if target is not None:
                target_name = target.name
        alert = await self.repository.find_alert(directive.alert_id)
        fulfilled_by_name = None
        if directive.fulfilled_by:
            find_user = getattr(self.repository, "find_user", None)
            if find_user is not None:
                fulfilled_by_user = await find_user(directive.fulfilled_by)
                if fulfilled_by_user is not None:
                    fulfilled_by_name = fulfilled_by_user.full_name
        return CoordinationDirectiveResponse(
            id=str(directive.id),
            alert_id=str(directive.alert_id),
            source_department_id=str(directive.source_department_id),
            source_department_name=source_name,
            target_department_id=str(directive.target_department_id),
            target_department_name=target_name,
            alert_title=alert.title if alert is not None else None,
            tasks_to_transfer=directive.tasks_to_transfer,
            note=directive.note,
            status=directive.status,
            issued_by=str(directive.issued_by),
            issued_at=directive.issued_at,
            fulfilled_plan_id=(
                str(directive.fulfilled_plan_id) if directive.fulfilled_plan_id else None
            ),
            fulfilled_by=str(directive.fulfilled_by) if directive.fulfilled_by else None,
            fulfilled_by_name=fulfilled_by_name,
            fulfilled_at=directive.fulfilled_at,
        )

    async def _plan_response(self, plan: CoordinationPlanDocument) -> CoordinationPlanResponse:
        target = await self.repository.find_employee(plan.target_employee_id)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên nhận việc"
            )
        return CoordinationPlanResponse(
            id=str(plan.id),
            alert_id=str(plan.alert_id),
            department_id=str(plan.department_id),
            target_department_id=str(plan.target_department_id or plan.department_id),
            source_employee_id=str(plan.source_employee_id),
            target_employee_id=str(plan.target_employee_id),
            target_employee_code=target.employee_code,
            target_employee_name=target.full_name,
            alert_date=plan.alert_date,
            tasks_to_transfer=plan.tasks_to_transfer,
            mode=plan.mode,
            note=plan.note,
            created_by=str(plan.created_by),
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )

    async def _suggestion_response(
        self,
        alert,
        alert_date,
        candidates: list[WorkloadCandidateResponse],
        plan: CoordinationPlanDocument | None,
    ) -> CoordinationSuggestionResponse:
        applied_plan = await self._plan_response(plan) if plan else None
        return CoordinationSuggestionResponse(
            alert_id=str(alert.id),
            alert_type=alert.alert_type,
            severity=alert.severity.value,
            alert_date=alert_date,
            source_employee_id=str(alert.employee_id),
            source_employee_code=alert.employee_code,
            source_employee_name=alert.employee_name,
            candidates=candidates,
            applied_plan=applied_plan,
        )

    @staticmethod
    def _select_candidate(
        candidates: list[WorkloadCandidateResponse], target_employee_id: str | None
    ) -> WorkloadCandidateResponse | None:
        if target_employee_id is None:
            return candidates[0] if candidates else None
        try:
            return next(
                candidate
                for candidate in candidates
                if candidate.employee_id == str(ObjectId(target_employee_id))
            )
        except (InvalidId, StopIteration):
            return None

    def _alert_date(self, alert) -> Any:
        if alert.detected_dates:
            return max(alert.detected_dates)
        return self._clock.today()

    @staticmethod
    def _parse_object_id(value: str, label: str) -> ObjectId:
        try:
            return ObjectId(value)
        except (InvalidId, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{label} không hợp lệ"
            ) from None


def get_coordination_service(database_provider: Callable[[], Any]) -> CoordinationService:
    database = database_provider()
    return CoordinationService(
        CoordinationRepository(database),
        department_repository=DepartmentRepository(database),
        clock=BusinessClock(),
    )


__all__ = ["CoordinationService", "get_coordination_service"]
