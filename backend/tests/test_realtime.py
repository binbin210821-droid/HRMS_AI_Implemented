import asyncio
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from starlette.websockets import WebSocketDisconnect

from app.events.event_bus import EventBus
from app.models.user import CurrentUser, UserRole
from app.realtime.change_stream_worker import (
    AlertsChangeStreamWorker,
    DepartmentEvaluationsChangeStreamWorker,
    PerformanceMetricsChangeStreamWorker,
    TaskDirectivesChangeStreamWorker,
    TaskExecutionReportsChangeStreamWorker,
    TasksChangeStreamWorker,
)
from app.realtime.connection_manager import ConnectionManager


class FakeWebSocket:
    def __init__(self, fail_on_send: bool = False) -> None:
        self.accepted = False
        self.messages: list[dict] = []
        self.fail_on_send = fail_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        if self.fail_on_send:
            raise WebSocketDisconnect()
        self.messages.append(message)


def current_user(user_id: str, role: UserRole, department_id: ObjectId | None) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        username=user_id,
        full_name=user_id,
        role=role,
        department_id=str(department_id) if department_id else None,
    )


@pytest.mark.asyncio
async def test_manager_receives_only_own_department_and_leadership_receives_all() -> None:
    manager = ConnectionManager()
    kd = ObjectId()
    kt = ObjectId()
    kd_socket = FakeWebSocket()
    kt_socket = FakeWebSocket()
    leadership_socket = FakeWebSocket()
    await manager.connect(kd_socket, current_user("manager-kd", UserRole.MANAGER, kd))
    await manager.connect(kt_socket, current_user("manager-kt", UserRole.MANAGER, kt))
    await manager.connect(leadership_socket, current_user("leadership", UserRole.LEADERSHIP, None))

    await manager.broadcast_alert_change(
        {
            "operationType": "insert",
            "fullDocument": {
                "_id": ObjectId(),
                "department_id": kd,
                "created_at": datetime.now(timezone.utc),
            },
        }
    )

    assert manager.connection_count == 3
    assert kd_socket.accepted and kt_socket.accepted and leadership_socket.accepted
    assert len(kd_socket.messages) == 1
    assert len(kt_socket.messages) == 0
    assert len(leadership_socket.messages) == 1
    assert kd_socket.messages[0]["topic"] == "alerts"
    assert isinstance(kd_socket.messages[0]["data"]["_id"], str)
    assert isinstance(kd_socket.messages[0]["data"]["created_at"], str)

    await manager.broadcast_task_change(
        {
            "operationType": "insert",
            "fullDocument": {"_id": ObjectId(), "department_id": kd},
        }
    )
    assert kd_socket.messages[-1]["topic"] == "tasks"
    assert len(kt_socket.messages) == 0
    assert len(leadership_socket.messages) == 2


@pytest.mark.asyncio
async def test_disconnect_and_failed_send_remove_connection() -> None:
    manager = ConnectionManager()
    department_id = ObjectId()
    socket = FakeWebSocket(fail_on_send=True)
    await manager.connect(socket, current_user("manager", UserRole.MANAGER, department_id))
    manager.disconnect(socket)
    assert manager.connection_count == 0

    await manager.connect(socket, current_user("manager", UserRole.MANAGER, department_id))
    await manager.broadcast_alert_change(
        {"operationType": "insert", "fullDocument": {"department_id": department_id}}
    )
    assert manager.connection_count == 0


class FakeChangeStream:
    def __init__(self, changes: list[dict]) -> None:
        self.changes = changes

    async def __aenter__(self) -> "FakeChangeStream":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    def __aiter__(self) -> "FakeChangeStream":
        return self

    async def __anext__(self) -> dict:
        if not self.changes:
            raise StopAsyncIteration
        return self.changes.pop(0)


class FakeAlertsCollection:
    def __init__(self, changes: list[dict]) -> None:
        self.stream = FakeChangeStream(changes)

    def watch(self, **_kwargs: str) -> FakeChangeStream:
        return self.stream


@pytest.mark.asyncio
async def test_change_stream_worker_publishes_alert_events() -> None:
    bus = EventBus()
    received: list[dict] = []

    async def capture(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("alerts.changed", capture)
    change = {"operationType": "insert", "fullDocument": {"department_id": ObjectId()}}
    worker = AlertsChangeStreamWorker(lambda: {"alerts": FakeAlertsCollection([change])}, bus=bus)

    await worker._watch_alerts(asyncio.Event())

    assert received == [change]


@pytest.mark.asyncio
async def test_task_directive_realtime_is_scoped_to_target_department() -> None:
    manager = ConnectionManager()
    target_department = ObjectId()
    other_department = ObjectId()
    target_socket = FakeWebSocket()
    other_socket = FakeWebSocket()
    leadership_socket = FakeWebSocket()
    await manager.connect(
        target_socket, current_user("manager-target", UserRole.MANAGER, target_department)
    )
    await manager.connect(
        other_socket, current_user("manager-other", UserRole.MANAGER, other_department)
    )
    await manager.connect(
        leadership_socket, current_user("leadership", UserRole.LEADERSHIP, None)
    )

    await manager.broadcast_task_directive_change(
        {
            "operationType": "insert",
            "fullDocument": {
                "_id": ObjectId(),
                "target_department_id": target_department,
            },
        }
    )

    assert target_socket.messages[0]["topic"] == "task_directives"
    assert other_socket.messages == []
    assert leadership_socket.messages[0]["topic"] == "task_directives"


@pytest.mark.asyncio
async def test_task_directive_change_stream_publishes_events() -> None:
    bus = EventBus()
    received: list[dict] = []

    async def capture(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("task_directives.changed", capture)
    change = {
        "operationType": "insert",
        "fullDocument": {"target_department_id": ObjectId()},
    }
    worker = TaskDirectivesChangeStreamWorker(
        lambda: {"department_task_directives": FakeAlertsCollection([change])}, bus=bus
    )

    await worker._watch_directives(asyncio.Event())

    assert received == [change]


@pytest.mark.asyncio
async def test_performance_change_stream_enriches_department_scope() -> None:
    bus = EventBus()
    received: list[dict] = []
    department_id = ObjectId()
    employee_id = ObjectId()

    async def capture(payload: dict) -> None:
        received.append(payload)

    class FakeEmployeeCollection:
        async def find_one(self, query: dict) -> dict:
            assert query == {"_id": employee_id}
            return {"_id": employee_id, "department_id": department_id}

    bus.subscribe("performance_metrics.changed", capture)
    change = {
        "operationType": "insert",
        "fullDocument": {"employee_id": employee_id, "performance_score": 86},
    }
    worker = PerformanceMetricsChangeStreamWorker(
        lambda: {
            "performance_metrics": FakeAlertsCollection([change]),
            "employees": FakeEmployeeCollection(),
        },
        bus=bus,
    )

    await worker._watch_metrics(asyncio.Event())

    assert received[0]["fullDocument"]["department_id"] == department_id


@pytest.mark.asyncio
async def test_tasks_change_stream_publishes_events_immediately() -> None:
    bus = EventBus()
    received: list[dict] = []

    async def capture(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("tasks.changed", capture)
    change = {
        "operationType": "insert",
        "fullDocument": {"_id": ObjectId(), "department_id": ObjectId()},
    }

    class FakeDatabase:
        def __getitem__(self, name: str) -> FakeAlertsCollection:
            assert name == "tasks"
            return FakeAlertsCollection([change])

        async def command(self, _command: dict) -> None:
            return None

    worker = TasksChangeStreamWorker(
        lambda: FakeDatabase(),
        bus=bus,
    )

    await worker._watch_tasks(asyncio.Event())

    assert received == [change]


@pytest.mark.asyncio
async def test_task_execution_report_change_stream_publishes_events() -> None:
    bus = EventBus()
    received: list[dict] = []

    async def capture(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("task_execution_reports.changed", capture)
    change = {
        "operationType": "update",
        "fullDocument": {"_id": ObjectId(), "employee_id": ObjectId()},
    }
    worker = TaskExecutionReportsChangeStreamWorker(
        lambda: {"task_execution_reports": FakeAlertsCollection([change])}, bus=bus
    )

    await worker._watch_reports(asyncio.Event())

    assert received == [change]


@pytest.mark.asyncio
async def test_department_evaluation_change_stream_publishes_events() -> None:
    bus = EventBus()
    received: list[dict] = []
    stop_event = asyncio.Event()

    async def capture(payload: dict) -> None:
        received.append(payload)
        stop_event.set()

    bus.subscribe("department_evaluations.changed", capture)
    change = {
        "operationType": "insert",
        "fullDocument": {"_id": ObjectId(), "department_id": ObjectId()},
    }
    class EvaluationCollection:
        def watch(self, **_kwargs: str) -> FakeChangeStream:
            return FakeChangeStream([change])

    worker = DepartmentEvaluationsChangeStreamWorker(
        lambda: {"department_weekly_evaluations": EvaluationCollection()}, bus=bus
    )

    await worker.run(stop_event)

    assert received == [change]
