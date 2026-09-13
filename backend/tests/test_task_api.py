from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_department_scope
from app.api.tasks import get_task_service
from app.main import app
from app.models.user import CurrentUser, UserRole


class ForbiddenMutationSentinel:
    async def create(self, *_args, **_kwargs):
        raise AssertionError("Service tạo công việc không được gọi với Leadership")


def test_leadership_cannot_call_personal_task_creation_api() -> None:
    leadership = CurrentUser(
        user_id="leadership-id",
        username="demo.leadership",
        full_name="Lãnh đạo",
        role=UserRole.LEADERSHIP,
        department_id=None,
    )
    app.dependency_overrides[get_current_user] = lambda: leadership
    app.dependency_overrides[get_department_scope] = lambda: None
    app.dependency_overrides[get_task_service] = lambda: ForbiddenMutationSentinel()
    try:
        response = TestClient(app).post(
            "/api/tasks",
            json={
                "title": "Không được tạo trực tiếp",
                "employee_id": "507f1f77bcf86cd799439011",
                "due_date": "2026-09-08",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json() == {
        "code": "forbidden",
        "message": "Bạn không có quyền thực hiện chức năng này",
        "details": None,
        "request_id": response.json()["request_id"],
    }
