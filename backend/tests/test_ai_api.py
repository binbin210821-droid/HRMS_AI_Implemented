from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bson import ObjectId
from fastapi.testclient import TestClient

from app.api.ai import (
    get_ai_leadership_context_service,
    get_ai_service,
    get_ai_tool_service,
)
from app.api.coordination import get_service as get_coordination_service
from app.api.dependencies import get_current_user, get_department_scope
from app.infrastructure.rate_limit import InMemoryRateLimiter, RateLimitKeyBuilder, RateLimitPolicy
from app.main import app
from app.models.user import CurrentUser, UserRole
from app.services.coordination_service import CoordinationService


class SafeFakeAiService:
    async def stream_response(self, _message: str, _scope) -> AsyncIterator[str]:
        yield "Trợ lý AI hiện chưa sẵn sàng. Vui lòng thử lại sau ít phút."


class ProposalFakeAiService:
    async def generate_alert_action_proposal(self, _alert, _scope, _candidates, _actor_id=None):
        return {"alert_id": "alert-1", "summary": "Đề xuất", "actions": []}


class ToolPreviewFakeAiService:
    async def preview_from_message(self, _message, _current_user, _scope):
        return "executed", "get_rebalance_candidates", {"candidates": []}, "Đã đọc dữ liệu."


class LeadershipProposalFakeAiService:
    async def generate_leadership_action_proposal(self, _context, actor_id=None):
        return {
            "summary": "Theo dõi phòng Kinh doanh.",
            "actions": [
                {
                    "type": "issue_department_directive",
                    "department_id": "department-1",
                    "department_name": "Kinh doanh",
                    "rationale": "Có rủi ro cần theo dõi.",
                }
            ],
        }


class LeadershipContextFakeService:
    async def build(self, _current_user):
        return object()


class OutsideScopeAlertRepository:
    async def find_alert(self, _alert_id):
        return SimpleNamespace(
            department_id=ObjectId(),
            status=SimpleNamespace(value="open"),
        )


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
    original_rate_limit_enabled = app.state.settings.rate_limit_enabled
    app.state.settings.rate_limit_enabled = False

    try:
        response = TestClient(app).post("/api/ai/chat/stream", json={"message": "Xin chào"})
    finally:
        app.state.settings.rate_limit_enabled = original_rate_limit_enabled
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    assert "Trợ lý AI hiện chưa sẵn sàng" in response.text
    assert "tasks_completed" not in response.text


def test_alert_ai_proposal_uses_enforced_ten_request_ai_quota() -> None:
    current_user = CurrentUser(
        user_id="manager-id",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id=str(ObjectId()),
    )
    department_id = ObjectId(current_user.department_id)
    coordination_service = SimpleNamespace(
        get_rebalance_candidates_for_alert=AsyncMock(return_value=(object(), []))
    )
    settings = app.state.settings
    original_settings = (
        settings.rate_limit_ai_chat,
        settings.rate_limit_enforced_groups,
        settings._rate_limit_enforced_groups_cache,
    )
    original_limiter = app.state.rate_limiter
    original_policy = app.state.rate_limit_policy
    original_key_builder = app.state.rate_limit_key_builder
    original_overrides = dict(app.dependency_overrides)
    limiter = InMemoryRateLimiter()
    settings.rate_limit_ai_chat = 10
    settings.rate_limit_enforced_groups = "ai_chat"
    settings._rate_limit_enforced_groups_cache = None
    app.state.rate_limiter = limiter
    app.state.rate_limit_policy = RateLimitPolicy(settings)
    app.state.rate_limit_key_builder = RateLimitKeyBuilder(settings)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_department_scope] = lambda: department_id
    app.dependency_overrides[get_coordination_service] = lambda: coordination_service
    app.dependency_overrides[get_ai_service] = lambda: ProposalFakeAiService()

    try:
        client = TestClient(app)
        url = "/api/v1/alerts/alert-1/ai-proposal"
        responses = [client.post(url) for _ in range(10)]
        denied = client.post(url)
    finally:
        settings.rate_limit_ai_chat = original_settings[0]
        settings.rate_limit_enforced_groups = original_settings[1]
        settings._rate_limit_enforced_groups_cache = original_settings[2]
        app.state.rate_limiter = original_limiter
        app.state.rate_limit_policy = original_policy
        app.state.rate_limit_key_builder = original_key_builder
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)

    assert all(response.status_code == 200 for response in responses)
    assert denied.status_code == 429


def test_alert_ai_proposal_returns_403_for_manager_outside_alert_department() -> None:
    current_user = CurrentUser(
        user_id="manager-id",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id=str(ObjectId()),
    )
    own_department_id = ObjectId(current_user.department_id)
    alert_id = str(ObjectId())
    settings = app.state.settings
    original_rate_limit_enabled = settings.rate_limit_enabled
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_department_scope] = lambda: own_department_id
    app.dependency_overrides[get_coordination_service] = lambda: CoordinationService(
        OutsideScopeAlertRepository()
    )
    app.dependency_overrides[get_ai_service] = lambda: ProposalFakeAiService()
    settings.rate_limit_enabled = False

    try:
        response = TestClient(app).post(f"/api/v1/alerts/{alert_id}/ai-proposal")
    finally:
        settings.rate_limit_enabled = original_rate_limit_enabled
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)

    assert response.status_code == 403


def test_ai_tool_preview_uses_same_ai_chat_rate_limit_and_service_contract() -> None:
    current_user = CurrentUser(
        user_id="manager-id",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id=str(ObjectId()),
    )
    settings = app.state.settings
    original_rate_limit_enabled = settings.rate_limit_enabled
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_department_scope] = lambda: ObjectId(current_user.department_id)
    app.dependency_overrides[get_ai_tool_service] = lambda: ToolPreviewFakeAiService()
    settings.rate_limit_enabled = False

    try:
        response = TestClient(app).post(
            "/api/v1/ai/tool-preview",
            json={"message": "Tìm ứng viên điều phối cho cảnh báo"},
        )
    finally:
        settings.rate_limit_enabled = original_rate_limit_enabled
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)

    assert response.status_code == 200
    assert response.json()["tool_name"] == "get_rebalance_candidates"
    assert response.json()["status"] == "executed"


def test_leadership_proposal_rejects_manager_with_403() -> None:
    current_user = CurrentUser(
        user_id="manager-id",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id=str(ObjectId()),
    )
    settings = app.state.settings
    original_rate_limit_enabled = settings.rate_limit_enabled
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: current_user
    settings.rate_limit_enabled = False

    try:
        response = TestClient(app).post("/api/v1/ai/leadership-proposal")
    finally:
        settings.rate_limit_enabled = original_rate_limit_enabled
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)

    assert response.status_code == 403


def test_leadership_proposal_returns_reviewable_draft() -> None:
    current_user = CurrentUser(
        user_id="leadership-id",
        username="leadership",
        full_name="Lãnh đạo",
        role=UserRole.LEADERSHIP,
    )
    settings = app.state.settings
    original_rate_limit_enabled = settings.rate_limit_enabled
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_ai_leadership_context_service] = (
        lambda: LeadershipContextFakeService()
    )
    app.dependency_overrides[get_ai_service] = lambda: LeadershipProposalFakeAiService()
    settings.rate_limit_enabled = False

    try:
        response = TestClient(app).post("/api/v1/ai/leadership-proposal")
    finally:
        settings.rate_limit_enabled = original_rate_limit_enabled
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)

    assert response.status_code == 200
    assert response.json()["actions"][0]["department_name"] == "Kinh doanh"
