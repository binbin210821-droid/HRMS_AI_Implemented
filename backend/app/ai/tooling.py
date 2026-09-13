from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from bson import ObjectId
from pydantic import BaseModel, ValidationError

from app.models.user import UserRole


class AiToolError(RuntimeError):
    """A safe, user-facing tool execution failure."""


class ToolNotAllowedError(AiToolError):
    pass


class ToolApprovalRequired(AiToolError):
    pass


class ToolAuditWriter(Protocol):
    async def insert_audit_log(self, document: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class ToolExecutionContext:
    user_id: str
    role: UserRole
    department_scope: ObjectId | None
    human_approval_token: str | None = None


ToolHandler = Callable[[Any, ToolExecutionContext], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class AiToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    allowed_roles: frozenset[UserRole]
    read_only: bool
    requires_human_approval: bool
    handler: ToolHandler | None = None

    @property
    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolExecutionResult:
    tool_name: str
    status: Literal["executed", "approval_required"]
    data: dict[str, Any] | None
    message: str


class AiToolRegistry:
    """Allowlisted tool execution with scope and approval gates."""

    def __init__(self, audit_writer: ToolAuditWriter | None = None) -> None:
        self._definitions: dict[str, AiToolDefinition] = {}
        self.audit_writer = audit_writer

    def register(self, definition: AiToolDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"Tool đã đăng ký: {definition.name}")
        if definition.read_only and definition.requires_human_approval:
            raise ValueError("Tool chỉ-đọc không được yêu cầu phê duyệt thay đổi")
        self._definitions[definition.name] = definition

    def definitions_for(self, role: UserRole) -> list[AiToolDefinition]:
        return [
            definition
            for definition in self._definitions.values()
            if role in definition.allowed_roles
        ]

    def definition(self, name: str) -> AiToolDefinition:
        definition = self._definitions.get(name)
        if definition is None:
            raise ToolNotAllowedError("AI không được phép gọi công cụ này")
        return definition

    async def execute(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
        *,
        human_approved: bool = False,
    ) -> ToolExecutionResult:
        definition = self.definition(call.name)
        if context.role not in definition.allowed_roles:
            raise ToolNotAllowedError("Bạn không có quyền sử dụng công cụ này")
        try:
            arguments = definition.input_model.model_validate(call.arguments)
        except ValidationError as error:
            raise ToolNotAllowedError("Tham số công cụ không hợp lệ") from error

        if definition.requires_human_approval:
            if not human_approved or not context.human_approval_token:
                await self._audit(
                    call,
                    context,
                    status="approval_required",
                    output_summary={"tool_name": call.name},
                )
                return ToolExecutionResult(
                    tool_name=call.name,
                    status="approval_required",
                    data=None,
                    message="Đề xuất cần người dùng kiểm tra và xác nhận thủ công.",
                )

        if definition.handler is None:
            raise AiToolError("Công cụ chưa có đường thực thi an toàn")

        try:
            data = await definition.handler(arguments, context)
        except AiToolError:
            raise
        except Exception as error:
            await self._audit(
                call,
                context,
                status="failed",
                output_summary={"error_type": type(error).__name__},
            )
            raise AiToolError("Chưa thể thực hiện công cụ lúc này") from error

        await self._audit(
            call,
            context,
            status="executed",
            output_summary={"keys": sorted(data), "item_count": _item_count(data)},
        )
        return ToolExecutionResult(
            tool_name=call.name,
            status="executed",
            data=data,
            message="Đã đọc dữ liệu trong đúng phạm vi được cấp quyền.",
        )

    async def _audit(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
        *,
        status: str,
        output_summary: dict[str, Any],
    ) -> None:
        if self.audit_writer is None:
            return
        await self.audit_writer.insert_audit_log(
            {
                "action": "ai_tool_call",
                "user_id": _object_id_or_string(context.user_id),
                "actor_id": _object_id_or_string(context.user_id),
                "department_id": context.department_scope,
                "tool_name": call.name,
                "status": status,
                "input_summary": {
                    "argument_keys": sorted(call.arguments),
                    "arguments_sha256": _sha256(call.arguments),
                },
                "output_summary": output_summary,
            }
        )


def _sha256(value: dict[str, Any]) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _object_id_or_string(value: str) -> ObjectId | str:
    try:
        return ObjectId(value)
    except Exception:
        return value


def _item_count(value: dict[str, Any]) -> int:
    for item in value.values():
        if isinstance(item, list):
            return len(item)
    return 0


__all__ = [
    "AiToolDefinition",
    "AiToolError",
    "AiToolRegistry",
    "ToolApprovalRequired",
    "ToolCall",
    "ToolExecutionContext",
    "ToolExecutionResult",
    "ToolNotAllowedError",
]
