import asyncio
import logging
from collections.abc import Callable
from typing import Any

from pymongo.errors import PyMongoError

from app.events.event_bus import (
    DEPARTMENT_DIRECTIVE_CHANGED,
    DEPARTMENT_EVALUATION_CHANGED,
    TASK_DIRECTIVE_CHANGED,
    TASK_EXECUTION_REPORT_CHANGED,
    EventBus,
    event_bus,
)

logger = logging.getLogger(__name__)
DatabaseProvider = Callable[[], Any]


class AlertsChangeStreamWorker:
    """Đọc Change Stream alerts rồi phát event hạ tầng cho WebSocket manager."""

    def __init__(
        self,
        database_provider: DatabaseProvider,
        bus: EventBus = event_bus,
        retry_delay: float = 1.0,
    ) -> None:
        self.database_provider = database_provider
        self.bus = bus
        self.retry_delay = retry_delay

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self._watch_alerts(stop_event)
            except asyncio.CancelledError:
                raise
            except PyMongoError:
                logger.exception("Change Stream alerts tạm thời không khả dụng; sẽ thử lại")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.retry_delay)
                except TimeoutError:
                    continue

    async def _watch_alerts(self, stop_event: asyncio.Event) -> None:
        collection = self.database_provider()["alerts"]
        async with collection.watch(full_document="updateLookup") as stream:
            async for change in stream:
                if stop_event.is_set():
                    return
                await self.bus.publish("alerts.changed", change)


class PerformanceMetricsChangeStreamWorker:
    """Đọc điểm hiệu suất mới và phát event hạ tầng cho dashboard realtime."""

    def __init__(
        self,
        database_provider: DatabaseProvider,
        bus: EventBus = event_bus,
        retry_delay: float = 1.0,
    ) -> None:
        self.database_provider = database_provider
        self.bus = bus
        self.retry_delay = retry_delay

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self._watch_metrics(stop_event)
            except asyncio.CancelledError:
                raise
            except PyMongoError:
                logger.exception(
                    "Change Stream performance_metrics tạm thời không khả dụng; sẽ thử lại"
                )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.retry_delay)
                except TimeoutError:
                    continue

    async def _watch_metrics(self, stop_event: asyncio.Event) -> None:
        database = self.database_provider()
        collection = database["performance_metrics"]
        employees = database["employees"]
        async with collection.watch(full_document="updateLookup") as stream:
            async for change in stream:
                if stop_event.is_set():
                    return
                full_document = change.get("fullDocument")
                if full_document and full_document.get("employee_id"):
                    employee = await employees.find_one({"_id": full_document["employee_id"]})
                    if employee:
                        full_document = dict(full_document)
                        full_document["department_id"] = employee.get("department_id")
                        change = dict(change)
                        change["fullDocument"] = full_document
                await self.bus.publish("performance_metrics.changed", change)


class TasksChangeStreamWorker:
    """Đọc thay đổi công việc và phát event realtime có sẵn department_id."""

    def __init__(
        self,
        database_provider: DatabaseProvider,
        bus: EventBus = event_bus,
        retry_delay: float = 1.0,
    ) -> None:
        self.database_provider = database_provider
        self.bus = bus
        self.retry_delay = retry_delay

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self._watch_tasks(stop_event)
            except asyncio.CancelledError:
                raise
            except PyMongoError:
                logger.exception("Change Stream tasks tạm thời không khả dụng; sẽ thử lại")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.retry_delay)
                except TimeoutError:
                    continue

    async def _watch_tasks(self, stop_event: asyncio.Event) -> None:
        database = self.database_provider()
        try:
            await database.command(
                {
                    "collMod": "tasks",
                    "changeStreamPreAndPostImages": {"enabled": True},
                }
            )
        except PyMongoError:
            logger.warning(
                "Không bật được pre-image cho tasks; sự kiện xóa trực tiếp có thể thiếu scope"
            )
        collection = database["tasks"]
        async with collection.watch(
            full_document="updateLookup",
            full_document_before_change="whenAvailable",
        ) as stream:
            async for change in stream:
                if stop_event.is_set():
                    return
                await self.bus.publish("tasks.changed", change)


class DepartmentDirectivesChangeStreamWorker:
    """Đọc chỉ thị cấp phòng ban và phát sự kiện realtime theo phòng đích."""

    def __init__(
        self,
        database_provider: DatabaseProvider,
        bus: EventBus = event_bus,
        retry_delay: float = 1.0,
    ) -> None:
        self.database_provider = database_provider
        self.bus = bus
        self.retry_delay = retry_delay

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self._watch_directives(stop_event)
            except asyncio.CancelledError:
                raise
            except PyMongoError:
                logger.exception(
                    "Change Stream chỉ thị phòng ban tạm thời không khả dụng; sẽ thử lại"
                )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.retry_delay)
                except TimeoutError:
                    continue

    async def _watch_directives(self, stop_event: asyncio.Event) -> None:
        collection = self.database_provider()["department_alert_directives"]
        async with collection.watch(full_document="updateLookup") as stream:
            async for change in stream:
                if stop_event.is_set():
                    return
                await self.bus.publish(DEPARTMENT_DIRECTIVE_CHANGED, change)


class TaskDirectivesChangeStreamWorker:
    """Đọc chỉ thị công việc cấp phòng ban và phát sự kiện theo phòng đích."""

    def __init__(
        self,
        database_provider: DatabaseProvider,
        bus: EventBus = event_bus,
        retry_delay: float = 1.0,
    ) -> None:
        self.database_provider = database_provider
        self.bus = bus
        self.retry_delay = retry_delay

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self._watch_directives(stop_event)
            except asyncio.CancelledError:
                raise
            except PyMongoError:
                logger.exception(
                    "Change Stream chỉ thị công việc tạm thời không khả dụng; sẽ thử lại"
                )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.retry_delay)
                except TimeoutError:
                    continue

    async def _watch_directives(self, stop_event: asyncio.Event) -> None:
        collection = self.database_provider()["department_task_directives"]
        async with collection.watch(full_document="updateLookup") as stream:
            async for change in stream:
                if stop_event.is_set():
                    return
                await self.bus.publish(TASK_DIRECTIVE_CHANGED, change)


class TaskExecutionReportsChangeStreamWorker:
    """Đọc thay đổi báo cáo thực thi để Manager cập nhật review đang mở."""

    def __init__(
        self,
        database_provider: DatabaseProvider,
        bus: EventBus = event_bus,
        retry_delay: float = 1.0,
    ) -> None:
        self.database_provider = database_provider
        self.bus = bus
        self.retry_delay = retry_delay

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self._watch_reports(stop_event)
            except asyncio.CancelledError:
                raise
            except PyMongoError:
                logger.exception(
                    "Change Stream báo cáo thực thi tạm thời không khả dụng; sẽ thử lại"
                )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.retry_delay)
                except TimeoutError:
                    continue

    async def _watch_reports(self, stop_event: asyncio.Event) -> None:
        collection = self.database_provider()["task_execution_reports"]
        async with collection.watch(
            full_document="updateLookup", full_document_before_change="whenAvailable"
        ) as stream:
            async for change in stream:
                if stop_event.is_set():
                    return
                await self.bus.publish(TASK_EXECUTION_REPORT_CHANGED, change)


class DepartmentEvaluationsChangeStreamWorker:
    """Phát thay đổi đánh giá tuần theo đúng phạm vi phòng ban."""

    def __init__(
        self,
        database_provider: DatabaseProvider,
        bus: EventBus = event_bus,
        retry_delay: float = 1.0,
    ) -> None:
        self.database_provider = database_provider
        self.bus = bus
        self.retry_delay = retry_delay

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                collection = self.database_provider()["department_weekly_evaluations"]
                async with collection.watch(full_document="updateLookup") as stream:
                    async for change in stream:
                        if stop_event.is_set():
                            return
                        await self.bus.publish(DEPARTMENT_EVALUATION_CHANGED, change)
            except asyncio.CancelledError:
                raise
            except PyMongoError:
                logger.exception(
                    "Change Stream đánh giá phòng ban tạm thời không khả dụng; sẽ thử lại"
                )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.retry_delay)
                except TimeoutError:
                    continue


def create_alerts_worker(database_provider: DatabaseProvider) -> AlertsChangeStreamWorker:
    return AlertsChangeStreamWorker(database_provider, event_bus)


def create_performance_metrics_worker(
    database_provider: DatabaseProvider,
) -> PerformanceMetricsChangeStreamWorker:
    return PerformanceMetricsChangeStreamWorker(database_provider, event_bus)


def create_tasks_worker(database_provider: DatabaseProvider) -> TasksChangeStreamWorker:
    return TasksChangeStreamWorker(database_provider, event_bus)


def create_department_directives_worker(
    database_provider: DatabaseProvider,
) -> DepartmentDirectivesChangeStreamWorker:
    return DepartmentDirectivesChangeStreamWorker(database_provider, event_bus)


def create_task_directives_worker(
    database_provider: DatabaseProvider,
) -> TaskDirectivesChangeStreamWorker:
    return TaskDirectivesChangeStreamWorker(database_provider, event_bus)


def create_task_execution_reports_worker(
    database_provider: DatabaseProvider,
) -> TaskExecutionReportsChangeStreamWorker:
    return TaskExecutionReportsChangeStreamWorker(database_provider, event_bus)


def create_department_evaluations_worker(
    database_provider: DatabaseProvider,
) -> DepartmentEvaluationsChangeStreamWorker:
    return DepartmentEvaluationsChangeStreamWorker(database_provider, event_bus)


__all__ = [
    "AlertsChangeStreamWorker",
    "DepartmentDirectivesChangeStreamWorker",
    "DepartmentEvaluationsChangeStreamWorker",
    "PerformanceMetricsChangeStreamWorker",
    "TaskDirectivesChangeStreamWorker",
    "TaskExecutionReportsChangeStreamWorker",
    "TasksChangeStreamWorker",
    "create_alerts_worker",
    "create_department_directives_worker",
    "create_department_evaluations_worker",
    "create_performance_metrics_worker",
    "create_task_directives_worker",
    "create_task_execution_reports_worker",
    "create_tasks_worker",
]
