from collections.abc import AsyncIterator

import pytest
from bson import ObjectId

from app.services.ai_service import AiService


class EmptyPerformanceRepository:
    def __init__(self) -> None:
        self.scope = None

    async def find_many(self, scope: ObjectId | None):
        self.scope = scope
        return []


class EmptyAlertRepository:
    async def find_many(self, scope, status=None, alert_type=None):
        return []


class EmptyOverloadRepository:
    async def list_logs(self, scope):
        return []


class CapturingFactory:
    def __init__(self) -> None:
        self.prompt = ""

    async def generate_insight_stream(self, prompt: str) -> AsyncIterator[str]:
        self.prompt = prompt
        yield "tasks_com"
        yield "pleted và quality_score đang được theo dõi."


@pytest.mark.asyncio
async def test_ai_service_passes_scoped_vietnamese_context_and_sanitizes_stream() -> None:
    performance = EmptyPerformanceRepository()
    factory = CapturingFactory()
    service = AiService(
        performance,
        EmptyAlertRepository(),
        EmptyOverloadRepository(),
        factory,
    )
    department_id = ObjectId()

    chunks = [chunk async for chunk in service.stream_response("Ai cần theo dõi?", department_id)]
    result = "".join(chunks)

    assert performance.scope == department_id
    assert "phòng ban của người dùng" in factory.prompt
    assert "tasks_completed" not in factory.prompt
    assert "tasks_completed" not in result
    assert "Số công việc hoàn thành" in result
    assert "Điểm chất lượng công việc" in result
