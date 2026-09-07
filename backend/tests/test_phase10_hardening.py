from collections.abc import AsyncIterator

import pytest
from bson import ObjectId

from app.ai.factory import SAFE_AI_FALLBACK_MESSAGE
from app.services.ai_service import AiService
from app.services.employee_service import EmployeeService


class BrokenAiFactory:
    async def generate_insight_stream(self, _prompt: str) -> AsyncIterator[str]:
        raise RuntimeError("AI provider is unavailable")
        yield ""


class EmptyPerformanceRepository:
    async def find_many(self, _scope):
        return []


class IndependentAlertRepository:
    def __init__(self) -> None:
        self.calls = 0

    async def find_many(self, _scope, status=None, alert_type=None):
        self.calls += 1
        return []


class IndependentOverloadRepository:
    async def list_logs(self, _scope):
        return []


class ScopeRecordingEmployeeRepository:
    def __init__(self) -> None:
        self.received_scope = None
        self.received_department = None

    async def find_many(self, scope, department_id=None):
        self.received_scope = scope
        self.received_department = department_id
        return []


@pytest.mark.asyncio
async def test_ai_outage_returns_fallback_and_does_not_block_alert_repository() -> None:
    alerts = IndependentAlertRepository()
    service = AiService(
        EmptyPerformanceRepository(),
        alerts,
        IndependentOverloadRepository(),
        BrokenAiFactory(),
    )

    result = "".join([chunk async for chunk in service.stream_response("Tóm tắt", ObjectId())])
    await alerts.find_many(ObjectId(), status="open")

    assert SAFE_AI_FALLBACK_MESSAGE in result
    assert alerts.calls == 2


@pytest.mark.asyncio
async def test_manager_scope_is_forwarded_when_client_requests_another_department() -> None:
    repository = ScopeRecordingEmployeeRepository()
    service = EmployeeService(repository)
    own_department = ObjectId()
    requested_department = ObjectId()

    await service.list(own_department, str(requested_department))

    assert repository.received_scope == own_department
    assert repository.received_department == requested_department
