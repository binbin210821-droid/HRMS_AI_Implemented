import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

EventHandler = Callable[[Any], Awaitable[None]]
logger = logging.getLogger(__name__)
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
        if handler not in self._handlers[event_name]:
            self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_name)
        if not handlers:
            return
        self._handlers[event_name] = [item for item in handlers if item is not handler]
        if not self._handlers[event_name]:
            self._handlers.pop(event_name, None)

    async def publish(self, event_name: str, payload: Any) -> None:
        handlers = tuple(self._handlers.get(event_name, []))
        if handlers:
            results = await asyncio.gather(
                *(handler(payload) for handler in handlers),
                return_exceptions=True,
            )
            for handler, result in zip(handlers, results, strict=True):
                if isinstance(result, BaseException):
                    logger.error(
                        "event_handler_failed event=%s handler=%s error_type=%s",
                        event_name,
                        getattr(handler, "__qualname__", repr(handler)),
                        type(result).__name__,
                        exc_info=(type(result), result, result.__traceback__),
                    )


event_bus = EventBus()
