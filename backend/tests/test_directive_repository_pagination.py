r"""Live MongoDB contract tests for deterministic directive pagination.

Run explicitly with a local MongoDB instance:
    $env:RUN_DIRECTIVE_REPOSITORY_TESTS = "1"
    backend\.venv\Scripts\python.exe -m pytest backend/tests/test_directive_repository_pagination.py -m integration -q
"""

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError

from app.repositories.coordination_repository import CoordinationRepository
from app.repositories.task_repository import TaskRepository

pytestmark = pytest.mark.integration


def _mongo_uri() -> str:
    return os.getenv(
        "DIRECTIVE_REPOSITORY_TEST_MONGO_URI",
        os.getenv("MONGO_URI", "mongodb://127.0.0.1:27018/?directConnection=true"),
    )


def _task_documents(ids: list[ObjectId], department_id: ObjectId, manager_id: ObjectId) -> list[dict]:
    return [
        {
            "_id": directive_id,
            "target_department_id": department_id,
            "target_manager_id": manager_id,
            "task_ids": [ObjectId()],
            "focus": "overdue",
            "selected_task_count": 1,
            "status": "accepted",
            "issued_by": ObjectId(),
            "issued_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        }
        for directive_id in ids
    ]


def _alert_documents(ids: list[ObjectId], department_id: ObjectId, manager_id: ObjectId) -> list[dict]:
    return [
        {
            "_id": directive_id,
            "department_id": department_id,
            "target_department_id": department_id,
            "target_manager_id": manager_id,
            "alert_ids": [ObjectId()],
            "selected_alert_type": "all",
            "selected_severity": "all",
            "selected_alert_count": 1,
            "selected_open_count": 1,
            "total_count": 1,
            "open_count": 1,
            "resolved_count": 0,
            "early_warning_count": 0,
            "overload_count": 1,
            "high_count": 1,
            "status": "accepted",
            "issued_by": ObjectId(),
            "issued_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        }
        for directive_id in ids
    ]


def _coordination_documents(
    ids: list[ObjectId], source_department_id: ObjectId, target_department_id: ObjectId
) -> list[dict]:
    return [
        {
            "_id": directive_id,
            "alert_id": ObjectId(),
            "source_department_id": source_department_id,
            "target_department_id": target_department_id,
            "tasks_to_transfer": 1,
            "status": "pending",
            "issued_by": ObjectId(),
            "issued_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        }
        for directive_id in ids
    ]


async def _read_all_pages(load_page, department_id: ObjectId, expected_ids: list[ObjectId]) -> None:
    pages = [
        await load_page(department_id, None, 0, 2),
        await load_page(department_id, None, 2, 2),
        await load_page(department_id, None, 4, 2),
    ]
    received_ids = [item.id for page in pages for item in page.items]
    assert len(received_ids) == len(expected_ids)
    assert len(set(received_ids)) == len(expected_ids)
    assert set(received_ids) == set(expected_ids)
    assert received_ids == sorted(expected_ids, reverse=True)
    assert [page.total for page in pages] == [len(expected_ids)] * 3


@pytest.mark.asyncio
async def test_all_directive_repositories_page_same_timestamp_records_deterministically() -> None:
    if os.getenv("RUN_DIRECTIVE_REPOSITORY_TESTS") != "1":
        pytest.skip("Đặt RUN_DIRECTIVE_REPOSITORY_TESTS=1 để chạy kiểm thử MongoDB thật.")

    client = AsyncIOMotorClient(_mongo_uri(), serverSelectionTimeoutMS=1500)
    database_name = f"hrms_directive_pagination_{uuid4().hex}"
    database = client[database_name]
    try:
        await client.admin.command("ping")
    except ServerSelectionTimeoutError:
        client.close()
        pytest.skip("Không kết nối được MongoDB cho kiểm thử repository pagination.")

    department_id = ObjectId()
    target_department_id = ObjectId()
    manager_id = ObjectId()
    task_ids = [ObjectId() for _ in range(5)]
    alert_ids = [ObjectId() for _ in range(5)]
    coordination_ids = [ObjectId() for _ in range(5)]
    try:
        await database["department_task_directives"].insert_many(
            _task_documents(task_ids, department_id, manager_id)
        )
        await database["department_alert_directives"].insert_many(
            _alert_documents(alert_ids, department_id, manager_id)
        )
        await database["coordination_directives"].insert_many(
            _coordination_documents(coordination_ids, department_id, target_department_id)
        )

        task_repository = TaskRepository(database)
        coordination_repository = CoordinationRepository(database)
        await _read_all_pages(
            task_repository.list_department_directives_page, department_id, task_ids
        )
        await _read_all_pages(
            coordination_repository.list_department_directives_page, department_id, alert_ids
        )
        await _read_all_pages(
            coordination_repository.list_directives_page, target_department_id, coordination_ids
        )
    finally:
        await client.drop_database(database_name)
        client.close()
