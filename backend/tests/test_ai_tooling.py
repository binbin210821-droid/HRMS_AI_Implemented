from typing import Any

import pytest
from bson import ObjectId

from app.ai.tooling import (
    AiToolDefinition,
    AiToolRegistry,
    ToolCall,
    ToolExecutionContext,
    ToolNotAllowedError,
)
from app.models.ai_tools import ApplyCoordinationToolInput, RebalanceCandidatesToolInput
from app.models.user import UserRole


class AuditSpy:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    async def insert_audit_log(self, document: dict[str, Any]) -> None:
        self.documents.append(document)


@pytest.mark.asyncio
async def test_registry_enforces_allowlist_role_and_writes_safe_audit() -> None:
    audit = AuditSpy()
    calls: list[dict[str, Any]] = []

    async def handler(arguments: RebalanceCandidatesToolInput, _context) -> dict[str, Any]:
        calls.append(arguments.model_dump())
        return {"candidates": [{"employee_name": "Nguyễn An"}]}

    registry = AiToolRegistry(audit_writer=audit)
    registry.register(
        AiToolDefinition(
            name="get_rebalance_candidates",
            description="Đọc ứng viên điều phối",
            input_model=RebalanceCandidatesToolInput,
            allowed_roles=frozenset({UserRole.MANAGER}),
            read_only=True,
            requires_human_approval=False,
            handler=handler,
        )
    )

    result = await registry.execute(
        ToolCall("get_rebalance_candidates", {"alert_id": "alert-1"}),
        ToolExecutionContext("507f1f77bcf86cd799439011", UserRole.MANAGER, ObjectId()),
    )

    assert result.status == "executed"
    assert calls == [{"alert_id": "alert-1"}]
    assert audit.documents[0]["action"] == "ai_tool_call"
    assert audit.documents[0]["input_summary"]["argument_keys"] == ["alert_id"]
    assert "alert-1" not in str(audit.documents[0])

    with pytest.raises(ToolNotAllowedError, match="quyền"):
        await registry.execute(
            ToolCall("get_rebalance_candidates", {"alert_id": "alert-1"}),
            ToolExecutionContext("507f1f77bcf86cd799439011", UserRole.LEADERSHIP, ObjectId()),
        )


@pytest.mark.asyncio
async def test_mutation_tool_stops_at_human_approval_gate() -> None:
    registry = AiToolRegistry()
    registry.register(
        AiToolDefinition(
            name="apply_coordination",
            description="Đề xuất điều phối, không tự áp dụng",
            input_model=ApplyCoordinationToolInput,
            allowed_roles=frozenset({UserRole.MANAGER}),
            read_only=False,
            requires_human_approval=True,
            handler=None,
        )
    )

    result = await registry.execute(
        ToolCall(
            "apply_coordination",
            {
                "alert_id": "alert-1",
                "target_employee_id": "employee-1",
                "tasks_to_transfer": 1,
            },
        ),
        ToolExecutionContext("507f1f77bcf86cd799439011", UserRole.MANAGER, ObjectId()),
    )

    assert result.status == "approval_required"
    assert result.data is None
