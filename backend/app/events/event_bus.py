import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

EventHandler = Callable[[Any], Awaitable[None]]
ALERT_CREATED = "ALERT_CREATED"
PERFORMANCE_METRIC_CREATED = "PERFORMANCE_METRIC_CREATED"
OVERLOAD_DETECTED = "OVERLOAD_DETECTED"
COORDINATION_APPLIED = "COORDINATION_APPLIED"
DEPARTMENT_DIRECTIVE_CHANGED = "department_directives.changed"
TASK_DIRECTIVE_CHANGED = "task_directives.changed"
TASK_EXECUTION_REPORT_CHANGED = "task_execution_reports.changed"
DEPARTMENT_EVALUATION_CHANGED = "department_evaluations.changed"


class EventBus:
    """Event bus tối giản cho giao tiếp nội bộ giữa các module nghiệp vụ."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)

    async def publish(self, event_name: str, payload: Any) -> None:
        handlers = self._handlers.get(event_name, [])
        if handlers:
            await asyncio.gather(*(handler(payload) for handler in handlers))


event_bus = EventBus()
