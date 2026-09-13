from datetime import date
from types import SimpleNamespace

import pytest
from bson import ObjectId

from app.services.manager_briefing_service import ManagerBriefingService


class FixedClock:
    def today(self):
        return date(2026, 9, 10)


class BriefingPerformanceRepository:
    def __init__(self, employee_id: ObjectId, department_id: ObjectId) -> None:
        self.employee_id = employee_id
        self.department_id = department_id

    async def find_many(self, _scope):
        return [
            SimpleNamespace(
                employee_id=self.employee_id,
                date=date(2026, 9, 9),
                performance_score=80,
                quality_score=84,
            ),
            SimpleNamespace(
                employee_id=self.employee_id,
                date=date(2026, 9, 10),
                performance_score=88,
                quality_score=90,
            ),
        ]

    async def list_employees(self, _scope):
        return [SimpleNamespace(id=self.employee_id, full_name="Nguyễn An")]


class BriefingAlertRepository:
    async def find_many(self, _scope, status=None):
        if status != "open":
            return []
        return [
            SimpleNamespace(
                employee_name="Nguyễn An",
                severity=SimpleNamespace(value="high"),
                title="Cảnh báo quá tải",
                message="Khối lượng công việc tăng cao.",
            )
        ]


class BriefingOverloadRepository:
    def __init__(self, employee_id: ObjectId) -> None:
        self.employee_id = employee_id

    async def list_logs(self, _scope):
        return [
            SimpleNamespace(
                employee_id=self.employee_id,
                date=date(2026, 9, 10),
                trigger_reason=[SimpleNamespace(value="task_volume")],
                tasks_completed=5,
                quality_score=88,
            )
        ]

    async def find_employees(self, _employee_ids):
        return {self.employee_id: SimpleNamespace(full_name="Nguyễn An")}


class BriefingTaskRepository:
    async def find_many(self, _scope, overdue_only=False):
        if not overdue_only:
            return []
        return [
            SimpleNamespace(
                title="Hoàn thiện báo cáo tuần",
                employee_id=ObjectId(),
                due_date=date(2026, 9, 8),
            )
        ]


@pytest.mark.asyncio
async def test_manager_briefing_prioritizes_scope_checked_operational_items() -> None:
    employee_id = ObjectId()
    department_id = ObjectId()
    service = ManagerBriefingService(
        BriefingPerformanceRepository(employee_id, department_id),
        BriefingAlertRepository(),
        BriefingOverloadRepository(employee_id),
        BriefingTaskRepository(),
        clock=FixedClock(),
    )

    result = await service.build(department_id)

    assert result["pham_vi"] == "phòng ban của người dùng"
    assert result["ky_du_lieu"]["den_ngay"] == "2026-09-10"
    assert result["tong_quan"] == {
        "Số nhân viên có ghi nhận": 1,
        "Điểm hiệu suất trung bình": 84.0,
        "Điểm chất lượng trung bình": 87.0,
        "Số cảnh báo đang mở": 1,
        "Số lượt ghi nhận quá tải": 1,
        "Số công việc quá hạn": 1,
    }
    assert result["điểm_cần_chú_ý"][0]["loại"] == "cảnh báo"
    assert "employee_id" not in str(result)

