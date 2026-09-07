from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bson import ObjectId
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.events.event_bus import event_bus
from app.models.user import CurrentUser, UserRole


@dataclass(slots=True)
class ConnectionInfo:
    websocket: WebSocket
    user_id: str
    role: UserRole
    department_id: ObjectId | None


class ConnectionManager:
    """Quản lý socket và áp dụng scope trước khi gửi sự kiện."""

    def __init__(self) -> None:
        self._connections: dict[int, ConnectionInfo] = {}

    async def connect(self, websocket: WebSocket, user: CurrentUser) -> None:
        await websocket.accept()
        department_id = ObjectId(user.department_id) if user.department_id else None
        self._connections[id(websocket)] = ConnectionInfo(
            websocket=websocket,
            user_id=user.user_id,
            role=user.role,
            department_id=department_id,
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.pop(id(websocket), None)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def connections(self) -> tuple[ConnectionInfo, ...]:
        return tuple(self._connections.values())

    async def broadcast_alert_change(self, change: dict[str, Any]) -> None:
        await self._broadcast_scoped_change("alerts", change)

    async def broadcast_performance_change(self, change: dict[str, Any]) -> None:
        await self._broadcast_scoped_change("performance_metrics", change)

    async def broadcast_task_change(self, change: dict[str, Any]) -> None:
        await self._broadcast_scoped_change("tasks", change)

    async def broadcast_department_directive_change(self, change: dict[str, Any]) -> None:
        document = change.get("fullDocument") or change.get("fullDocumentBeforeChange") or {}
        department_id = self._read_department_id(
            document.get("target_department_id") or document.get("department_id")
        )
        await self._broadcast_scoped_change("department_directives", change, department_id)

    async def broadcast_task_directive_change(self, change: dict[str, Any]) -> None:
        document = change.get("fullDocument") or change.get("fullDocumentBeforeChange") or {}
        department_id = self._read_department_id(document.get("target_department_id"))
        await self._broadcast_scoped_change("task_directives", change, department_id)

    async def broadcast_task_execution_report_change(self, change: dict[str, Any]) -> None:
        document = change.get("fullDocument") or change.get("fullDocumentBeforeChange") or {}
        department_id = self._read_department_id(document.get("department_id"))
        await self._broadcast_scoped_change("task_execution_reports", change, department_id)

    async def broadcast_department_evaluation_change(self, change: dict[str, Any]) -> None:
        document = change.get("fullDocument") or change.get("fullDocumentBeforeChange") or {}
        department_id = self._read_department_id(document.get("department_id"))
        await self._broadcast_scoped_change("department_evaluations", change, department_id)

    async def _broadcast_scoped_change(
        self,
        topic: str,
        change: dict[str, Any],
        department_id: ObjectId | None = None,
    ) -> None:
        document = change.get("fullDocument") or change.get("fullDocumentBeforeChange") or {}
        department_id = department_id or self._read_department_id(document.get("department_id"))
        payload = {
            "topic": topic,
            "operation": change.get("operationType", "unknown"),
            "data": self._json_safe(document or change.get("documentKey", {})),
        }

        for connection in self.connections():
            if not self._can_receive(connection, department_id):
                continue
            try:
                await connection.websocket.send_json(payload)
            except (ConnectionError, OSError, RuntimeError, WebSocketDisconnect):
                self.disconnect(connection.websocket)

    @staticmethod
    def _can_receive(connection: ConnectionInfo, department_id: ObjectId | None) -> bool:
        if connection.role == UserRole.LEADERSHIP:
            return True
        return department_id is not None and connection.department_id == department_id

    @staticmethod
    def _read_department_id(value: Any) -> ObjectId | None:
        if isinstance(value, ObjectId):
            return value
        if isinstance(value, str):
            try:
                return ObjectId(value)
            except (TypeError, ValueError):
                return None
        return None

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_safe(item) for item in value]
        return value


realtime_manager = ConnectionManager()
event_bus.subscribe("alerts.changed", realtime_manager.broadcast_alert_change)
event_bus.subscribe("performance_metrics.changed", realtime_manager.broadcast_performance_change)
event_bus.subscribe("tasks.changed", realtime_manager.broadcast_task_change)
event_bus.subscribe(
    "department_directives.changed", realtime_manager.broadcast_department_directive_change
)
event_bus.subscribe("task_directives.changed", realtime_manager.broadcast_task_directive_change)
event_bus.subscribe(
    "task_execution_reports.changed", realtime_manager.broadcast_task_execution_report_change
)
event_bus.subscribe(
    "department_evaluations.changed", realtime_manager.broadcast_department_evaluation_change
)


__all__ = ["ConnectionInfo", "ConnectionManager", "realtime_manager"]
