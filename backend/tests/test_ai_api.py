from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.api.ai import get_ai_service
from app.api.dependencies import get_current_user, get_department_scope
from app.main import app
from app.models.user import CurrentUser, UserRole


class SafeFakeAiService:
    async def stream_response(self, _message: str, _scope) -> AsyncIterator[str]:
        yield "Trợ lý AI hiện chưa sẵn sàng. Vui lòng thử lại sau ít phút."


def test_ai_sse_returns_safe_vietnamese_response() -> None:
    current_user = CurrentUser(
        user_id="manager-id",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id="department-id",
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_department_scope] = lambda: None
    app.dependency_overrides[get_ai_service] = lambda: SafeFakeAiService()

    try:
        response = TestClient(app).post("/api/ai/chat/stream", json={"message": "Xin chào"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "Trợ lý AI hiện chưa sẵn sàng" in response.text
    assert "tasks_completed" not in response.text
