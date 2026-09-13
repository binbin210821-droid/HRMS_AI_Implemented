from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.events.event_bus import COORDINATION_APPLIED, EventBus
from app.models.alert import AlertDocument, AlertSeverity, AlertStatus
from app.models.coordination import (
    AcknowledgeDepartmentAlertDirectiveRequest,
    ApplyCoordinationRequest,
    CoordinationDirectiveDocument,
    CoordinationDirectiveStatus,
    CoordinationMode,
    DepartmentAlertDirectiveStatus,
    FulfillDirectiveRequest,
    IssueDepartmentAlertDirectiveRequest,
    ReviewDepartmentAlertDirectiveRequest,
    SubmitDepartmentAlertDirectiveRequest,
)
from app.models.employee import EmployeeDocument
from app.models.overload import WorkloadCandidateResponse
from app.services.coordination_service import CoordinationService


def make_alert(department_id: ObjectId) -> AlertDocument:
    now = datetime.now(timezone.utc)
    return AlertDocument(
        _id=ObjectId(),
        alert_type="overload",
        severity=AlertSeverity.HIGH,
        status=AlertStatus.OPEN,
        employee_id=ObjectId(),
        department_id=department_id,
        employee_code="KD-NV-001",
        employee_name="Nhân viên nguồn",
        title="Cảnh báo quá tải",
        message="Khối lượng công việc cao.",
        suggested_action="Phân bổ bớt công việc.",
        detected_dates=[date(2026, 9, 1)],
        fingerprint="coordination-test",
        created_at=now,
        updated_at=now,
    )


def make_employee(department_id: ObjectId, employee_id: ObjectId) -> EmployeeDocument:
    now = datetime.now(timezone.utc)
    return EmployeeDocument(
        _id=employee_id,
        employee_code="KD-NV-002",
        full_name="Nhân viên nhận việc",
        position="Chuyên viên",
        department_id=department_id,
        created_at=now,
        updated_at=now,
    )


class FakeRepository:
    def __init__(self, alert: AlertDocument, candidate: WorkloadCandidateResponse) -> None:
        self.alert = alert
        self.candidate = candidate
        self.plan = None
        self.audit_logs: list[dict] = []

    async def ensure_indexes(self):
        return None

    async def find_alert(self, _alert_id):
        return self.alert

    async def find_plan(self, _alert_id):
        return self.plan

    async def find_rebalance_candidates(self, _department_id, _metric_date, _excluded_id):
        return [self.candidate]

    async def insert_plan(self, document):
        from app.models.coordination import CoordinationPlanDocument

        self.plan = CoordinationPlanDocument.model_validate(document)
        return self.plan

    async def insert_audit_log(self, document, session=None):
        self.audit_logs.append(document)

    async def resolve_alert_for_coordination(
        self, _alert_id, resolved_by, resolution_note, resolved_at
    ):
        self.alert = self.alert.model_copy(
            update={
                "status": AlertStatus.RESOLVED,
                "resolved_by": resolved_by,
                "resolution_note": resolution_note,
                "resolved_at": resolved_at,
                "updated_at": resolved_at,
            }
        )
        return self.alert

    async def find_employee(self, employee_id):
        return make_employee(self.alert.department_id, employee_id)


class NameLookupRepository(FakeRepository):
    async def find_user(self, _user_id):
        return SimpleNamespace(full_name="Quản lý điều phối")


class NameLookupDepartmentRepository:
    async def find_by_id(self, department_id):
        return SimpleNamespace(name=f"Phòng {department_id}")


class TransactionalFakeClient:
    def __init__(self, repository):
        self.repository = repository

    async def start_session(self):
        return TransactionalFakeSession(self.repository)


class TransactionalFakeSession:
    def __init__(self, repository):
        self.repository = repository
        self._snapshot = None

    def start_transaction(self):
        return self

    async def __aenter__(self):
        self._snapshot = (
            self.repository.plan,
            self.repository.alert,
            list(self.repository.audit_logs),
        )
        return self

    async def __aexit__(self, exc_type, _exc_value, _traceback):
        if exc_type is not None:
            self.repository.plan, self.repository.alert, audit_logs = self._snapshot
            self.repository.audit_logs = audit_logs
        return False


class MidStepFailureRepository(FakeRepository):
    def __init__(self, alert, candidate):
        super().__init__(alert, candidate)
        self.client = TransactionalFakeClient(self)
        self.fail_once = True

    async def insert_plan(self, document, session=None):
        return await super().insert_plan(document)

    async def resolve_alert_for_coordination(
        self, alert_id, resolved_by, resolution_note, resolved_at, session=None
    ):
        if self.fail_once:
            self.fail_once = False
            return None
        return await super().resolve_alert_for_coordination(
            alert_id, resolved_by, resolution_note, resolved_at
        )


class MidStepDirectiveRepository(MidStepFailureRepository):
    def __init__(self, alert, candidate, directive):
        super().__init__(alert, candidate)
        self.directive = directive

    async def find_directive(self, _directive_id):
        return self.directive

    async def mark_directive_fulfilled(
        self, _directive_id, plan_id, fulfilled_by, fulfilled_at, session=None
    ):
        self.directive = self.directive.model_copy(
            update={
                "status": CoordinationDirectiveStatus.FULFILLED,
                "fulfilled_plan_id": plan_id,
                "fulfilled_by": fulfilled_by,
                "fulfilled_at": fulfilled_at,
            }
        )
        return self.directive


class FakeDepartmentDirectiveRepository:
    def __init__(self, department_id: ObjectId, alerts: list[AlertDocument]) -> None:
        self.department_id = department_id
        self.alerts = alerts
        self.directive = None
        self.directives = []
        self.audit_logs: list[dict] = []
        self.manager = SimpleNamespace(id=ObjectId(), full_name="Quản lý phòng ban")

    async def ensure_indexes(self):
        return None

    async def find_department(self, department_id):
        if department_id != self.department_id:
            return None
        return SimpleNamespace(name="Kinh doanh", is_active=True)

    async def find_active_manager_by_department(self, department_id):
        return self.manager if department_id == self.department_id else None

    async def find_pending_department_directive(self, department_id):
        if (
            self.directive
            and self.directive.target_department_id == department_id
            and self.directive.status == DepartmentAlertDirectiveStatus.PENDING
        ):
            return self.directive
        return None

    async def list_pending_department_directives(self, department_id):
        return [
            directive
            for directive in self.directives
            if directive.target_department_id == department_id
            and directive.status == DepartmentAlertDirectiveStatus.PENDING
        ]

    async def list_alerts_by_department(
        self, department_id, status=None, alert_type=None, severity=None
    ):
        return [
            alert
            for alert in self.alerts
            if alert.department_id == department_id
            and (status is None or alert.status.value == status)
            and (alert_type is None or alert.alert_type == alert_type)
            and (severity is None or alert.severity.value == severity)
        ]

    async def find_alerts_by_ids(self, alert_ids):
        return [alert for alert in self.alerts if alert.id in alert_ids]

    async def insert_department_directive(self, document):
        from app.models.coordination import DepartmentAlertDirectiveDocument

        self.directive = DepartmentAlertDirectiveDocument.model_validate(document)
        self.directives.append(self.directive)
        return self.directive

    async def find_department_directive(self, directive_id):
        return next(
            (directive for directive in self.directives if directive.id == directive_id), None
        )

    async def acknowledge_department_directive(
        self,
        _directive_id,
        acknowledged_by,
        acknowledged_at,
        acknowledgement_note,
        commitment_date,
    ):
        directive = await self.find_department_directive(_directive_id)
        if directive is None:
            return None
        acknowledged = directive.model_copy(
            update={
                "status": DepartmentAlertDirectiveStatus.ACKNOWLEDGED,
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": acknowledged_at,
                "acknowledgement_note": acknowledgement_note,
                "commitment_date": commitment_date,
            }
        )
        self.directives = [
            acknowledged if item.id == acknowledged.id else item for item in self.directives
        ]
        self.directive = acknowledged
        return acknowledged

    async def transition_department_directive(self, directive_id, expected_statuses, values):
        directive = await self.find_department_directive(directive_id)
        if directive is None or directive.status.value not in expected_statuses:
            return None
        updated = directive.model_dump(by_alias=True)
        updated.update(values)
        from app.models.coordination import DepartmentAlertDirectiveDocument

        updated_directive = DepartmentAlertDirectiveDocument.model_validate(updated)
        self.directives = [
            updated_directive if item.id == directive_id else item for item in self.directives
        ]
        self.directive = updated_directive
        return updated_directive

    async def list_department_directives(self, _scope, _status=None):
        return [
            directive
            for directive in self.directives
            if _status is None or directive.status.value == _status
        ]

    async def insert_audit_log(self, document):
        self.audit_logs.append(document)


@pytest.mark.asyncio
async def test_apply_suggestion_writes_plan_audit_and_event():
    department_id = ObjectId()
    alert = make_alert(department_id)
    target_id = ObjectId()
    candidate = WorkloadCandidateResponse(
        employee_id=str(target_id),
        employee_code="KD-NV-002",
        employee_name="Nhân viên nhận việc",
        tasks_completed=1,
        quality_score=90,
    )
    bus = EventBus()
    events = []

    async def capture(payload):
        events.append(payload)

    bus.subscribe(COORDINATION_APPLIED, capture)
    repository = FakeRepository(alert, candidate)
    plan = await CoordinationService(repository, bus).apply(
        str(alert.id),
        department_id,
        str(ObjectId()),
        ApplyCoordinationRequest(),
    )

    assert plan.target_employee_id == str(target_id)
    assert plan.tasks_to_transfer == 2
    assert plan.mode == CoordinationMode.SUGGESTED
    assert repository.audit_logs[0]["action"] == "workload_coordination_applied"
    assert events[0] == repository.plan
    assert repository.alert.status == AlertStatus.RESOLVED
    assert repository.alert.resolved_at is not None
    assert "Đã áp dụng điều phối" in repository.alert.resolution_note


@pytest.mark.asyncio
async def test_directive_response_includes_fulfilled_by_name_and_keeps_pending_null():
    department_id = ObjectId()
    alert = make_alert(department_id)
    candidate = WorkloadCandidateResponse(
        employee_id=str(ObjectId()),
        employee_code="KD-NV-002",
        employee_name="Nhân viên nhận việc",
        tasks_completed=1,
        quality_score=90,
    )
    fulfilled_by = ObjectId()
    repository = NameLookupRepository(alert, candidate)
    service = CoordinationService(repository, department_repository=NameLookupDepartmentRepository())
    base = {
        "_id": ObjectId(),
        "alert_id": alert.id,
        "source_department_id": department_id,
        "target_department_id": ObjectId(),
        "tasks_to_transfer": 1,
        "note": "Điều phối",
        "issued_by": ObjectId(),
        "issued_at": datetime(2026, 9, 10, 8, tzinfo=timezone.utc),
    }

    pending = await service._directive_response(
        CoordinationDirectiveDocument(**base, status=CoordinationDirectiveStatus.PENDING)
    )
    fulfilled = await service._directive_response(
        CoordinationDirectiveDocument(
            **base,
            status=CoordinationDirectiveStatus.FULFILLED,
            fulfilled_by=fulfilled_by,
            fulfilled_at=datetime(2026, 9, 10, 10, tzinfo=timezone.utc),
        )
    )

    assert pending.fulfilled_by is None
    assert pending.fulfilled_by_name is None
    assert fulfilled.fulfilled_by == str(fulfilled_by)
    assert fulfilled.fulfilled_by_name == "Quản lý điều phối"


@pytest.mark.asyncio
async def test_apply_transaction_rolls_back_mid_step_and_identical_retry_recovers():
    department_id = ObjectId()
    alert = make_alert(department_id)
    target_id = ObjectId()
    candidate = WorkloadCandidateResponse(
        employee_id=str(target_id),
        employee_code="KD-NV-002",
        employee_name="Nhân viên nhận việc",
        tasks_completed=1,
        quality_score=90,
    )
    repository = MidStepFailureRepository(alert, candidate)
    service = CoordinationService(repository)
    request = ApplyCoordinationRequest()

    with pytest.raises(HTTPException) as first_error:
        await service.apply(str(alert.id), department_id, str(ObjectId()), request)
    assert first_error.value.status_code == 503
    assert repository.plan is None
    assert repository.alert.status == AlertStatus.OPEN
    assert repository.audit_logs == []

    result = await service.apply(str(alert.id), department_id, str(ObjectId()), request)
    assert result.target_employee_id == str(target_id)
    assert repository.alert.status == AlertStatus.RESOLVED


@pytest.mark.asyncio
async def test_fulfill_transaction_rolls_back_mid_step_and_identical_retry_recovers():
    source_department_id = ObjectId()
    target_department_id = ObjectId()
    alert = make_alert(source_department_id)
    target_id = ObjectId()
    candidate = WorkloadCandidateResponse(
        employee_id=str(target_id),
        employee_code="CSKH-NV-002",
        employee_name="Nhân viên tiếp nhận",
        tasks_completed=1,
        quality_score=90,
    )
    directive = CoordinationDirectiveDocument(
        _id=ObjectId(),
        alert_id=alert.id,
        source_department_id=source_department_id,
        target_department_id=target_department_id,
        tasks_to_transfer=2,
        note="Xử lý cảnh báo liên phòng ban",
        status=CoordinationDirectiveStatus.PENDING,
        issued_by=ObjectId(),
        issued_at=datetime.now(timezone.utc),
    )
    repository = MidStepDirectiveRepository(alert, candidate, directive)
    service = CoordinationService(repository)
    request = FulfillDirectiveRequest(target_employee_id=str(target_id), tasks_to_transfer=1)

    with pytest.raises(HTTPException) as first_error:
        await service.fulfill_directive(
            str(directive.id), target_department_id, str(ObjectId()), request
        )
    assert first_error.value.status_code == 503
    assert repository.plan is None
    assert repository.alert.status == AlertStatus.OPEN
    assert repository.directive.status == CoordinationDirectiveStatus.PENDING

    result = await service.fulfill_directive(
        str(directive.id), target_department_id, str(ObjectId()), request
    )
    assert result.target_employee_id == str(target_id)
    assert repository.alert.status == AlertStatus.RESOLVED
    assert repository.directive.status == CoordinationDirectiveStatus.FULFILLED


@pytest.mark.asyncio
async def test_manager_cannot_apply_coordination_outside_department():
    alert_department = ObjectId()
    alert = make_alert(alert_department)
    candidate = WorkloadCandidateResponse(
        employee_id=str(ObjectId()),
        employee_code="KD-NV-002",
        employee_name="Nhân viên nhận việc",
        tasks_completed=1,
        quality_score=90,
    )

    with pytest.raises(HTTPException) as forbidden:
        await CoordinationService(FakeRepository(alert, candidate)).apply(
            str(alert.id),
            ObjectId(),
            str(ObjectId()),
            ApplyCoordinationRequest(),
        )

    assert forbidden.value.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_request_open_alert_outside_department():
    alert_department = ObjectId()
    alert = make_alert(alert_department)
    candidate = WorkloadCandidateResponse(
        employee_id=str(ObjectId()),
        employee_code="KD-NV-002",
        employee_name="Nhân viên nhận việc",
        tasks_completed=1,
        quality_score=90,
    )

    with pytest.raises(HTTPException) as forbidden:
        await CoordinationService(FakeRepository(alert, candidate)).get_open_alert(
            str(alert.id), ObjectId()
        )

    assert forbidden.value.status_code == 403


@pytest.mark.asyncio
async def test_leadership_cannot_apply_employee_coordination():
    department_id = ObjectId()
    alert = make_alert(department_id)
    candidate = WorkloadCandidateResponse(
        employee_id=str(ObjectId()),
        employee_code="KD-NV-002",
        employee_name="Nhân viên nhận việc",
        tasks_completed=1,
        quality_score=90,
    )

    with pytest.raises(HTTPException) as forbidden:
        await CoordinationService(FakeRepository(alert, candidate)).apply(
            str(alert.id), None, str(ObjectId()), ApplyCoordinationRequest()
        )

    assert forbidden.value.status_code == 403


@pytest.mark.asyncio
async def test_department_directive_snapshots_selected_open_alerts():
    department_id = ObjectId()
    high_overload = make_alert(department_id)
    medium_early = high_overload.model_copy(
        update={"_id": ObjectId(), "alert_type": "early_warning", "severity": AlertSeverity.MEDIUM}
    )
    repository = FakeDepartmentDirectiveRepository(department_id, [high_overload, medium_early])
    directive = await CoordinationService(repository).issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentAlertDirectiveRequest(alert_type="overload", severity="high"),
    )

    assert directive.department_id == str(department_id)
    assert directive.target_department_id == str(department_id)
    assert directive.target_manager_name == "Quản lý phòng ban"
    assert directive.selected_alert_count == 1
    assert directive.open_count == 2
    assert directive.status == DepartmentAlertDirectiveStatus.PENDING


@pytest.mark.asyncio
async def test_department_allows_pending_directives_for_different_alert_types():
    department_id = ObjectId()
    overload = make_alert(department_id)
    early_warning = overload.model_copy(
        update={"id": ObjectId(), "alert_type": "early_warning", "severity": AlertSeverity.MEDIUM}
    )
    repository = FakeDepartmentDirectiveRepository(department_id, [overload, early_warning])
    service = CoordinationService(repository)

    overload_directive = await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentAlertDirectiveRequest(alert_type="overload", severity="high"),
    )
    early_warning_directive = await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentAlertDirectiveRequest(alert_type="early_warning", severity="medium"),
    )

    assert overload_directive.id != early_warning_directive.id
    with pytest.raises(HTTPException) as duplicate:
        await service.issue_department_directive(
            str(department_id),
            str(ObjectId()),
            IssueDepartmentAlertDirectiveRequest(alert_type="early_warning", severity="medium"),
        )
    assert duplicate.value.status_code == 409


@pytest.mark.asyncio
async def test_department_does_not_reissue_alert_already_sent_in_acknowledged_directive():
    department_id = ObjectId()
    alert = make_alert(department_id)
    repository = FakeDepartmentDirectiveRepository(department_id, [alert])
    service = CoordinationService(repository)

    created = await service.issue_department_directive(
        str(department_id),
        str(ObjectId()),
        IssueDepartmentAlertDirectiveRequest(alert_type="overload", severity="high"),
    )
    await service.acknowledge_department_directive(
        created.id,
        department_id,
        str(repository.manager.id),
        AcknowledgeDepartmentAlertDirectiveRequest(commitment_date=date.today()),
    )

    with pytest.raises(HTTPException) as duplicate:
        await service.issue_department_directive(
            str(department_id),
            str(ObjectId()),
            IssueDepartmentAlertDirectiveRequest(alert_type="overload", severity="high"),
        )

    assert duplicate.value.status_code == 409


@pytest.mark.asyncio
async def test_manager_acknowledges_directive_without_resolving_alerts():
    department_id = ObjectId()
    alert = make_alert(department_id)
    repository = FakeDepartmentDirectiveRepository(department_id, [alert])
    service = CoordinationService(repository)
    created = await service.issue_department_directive(
        str(department_id), str(ObjectId()), IssueDepartmentAlertDirectiveRequest()
    )

    acknowledged = await service.acknowledge_department_directive(
        created.id,
        department_id,
        str(repository.manager.id),
        AcknowledgeDepartmentAlertDirectiveRequest(
            note="Đã tiếp nhận.", commitment_date=date.today()
        ),
    )

    assert acknowledged.status == DepartmentAlertDirectiveStatus.ACKNOWLEDGED
    assert acknowledged.acknowledgement_note == "Đã tiếp nhận."
    assert alert.status == AlertStatus.OPEN
    assert repository.audit_logs[-1]["action"] == "department_alert_directive_acknowledged"


@pytest.mark.asyncio
async def test_manager_cannot_acknowledge_directive_outside_department():
    department_id = ObjectId()
    alert = make_alert(department_id)
    repository = FakeDepartmentDirectiveRepository(department_id, [alert])
    service = CoordinationService(repository)
    created = await service.issue_department_directive(
        str(department_id), str(ObjectId()), IssueDepartmentAlertDirectiveRequest()
    )

    with pytest.raises(HTTPException) as forbidden:
        await service.acknowledge_department_directive(
            created.id,
            ObjectId(),
            str(repository.manager.id),
            AcknowledgeDepartmentAlertDirectiveRequest(commitment_date=date.today()),
        )

    assert forbidden.value.status_code == 403


@pytest.mark.asyncio
async def test_alert_directive_revision_and_acceptance_keep_alert_state_unchanged():
    department_id = ObjectId()
    alert = make_alert(department_id)
    repository = FakeDepartmentDirectiveRepository(department_id, [alert])
    service = CoordinationService(repository)
    created = await service.issue_department_directive(
        str(department_id), str(ObjectId()), IssueDepartmentAlertDirectiveRequest()
    )
    acknowledged = await service.acknowledge_department_directive(
        created.id,
        department_id,
        str(repository.manager.id),
        AcknowledgeDepartmentAlertDirectiveRequest(
            note="Đã tiếp nhận.", commitment_date=date.today()
        ),
    )
    repository.alerts[0] = alert.model_copy(update={"status": AlertStatus.RESOLVED})

    submitted = await service.submit_department_directive(
        created.id,
        department_id,
        str(repository.manager.id),
        SubmitDepartmentAlertDirectiveRequest(completion_note="Đã xử lý toàn bộ."),
    )
    revised = await service.request_department_directive_revision(
        submitted.id,
        str(ObjectId()),
        ReviewDepartmentAlertDirectiveRequest(note="Bổ sung bằng chứng xử lý."),
    )
    resubmitted = await service.submit_department_directive(
        revised.id,
        department_id,
        str(repository.manager.id),
        SubmitDepartmentAlertDirectiveRequest(),
    )
    accepted = await service.accept_department_directive(
        resubmitted.id,
        str(ObjectId()),
        ReviewDepartmentAlertDirectiveRequest(note="Đạt yêu cầu."),
    )

    assert submitted.progress_percent == 100
    assert revised.status.value == "needs_revision"
    assert accepted.status.value == "accepted"
    assert accepted.acknowledged_at == acknowledged.acknowledged_at
    assert repository.alerts[0].status == AlertStatus.RESOLVED
