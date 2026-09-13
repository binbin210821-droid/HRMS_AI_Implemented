import pytest
from bson import ObjectId

from app.models.task import ACTIVE_DIRECTIVE_STATUSES
from app.repositories.task_repository import TaskRepository


class FakeCollection:
    def __init__(self) -> None:
        self.index_calls: list[tuple[object, dict]] = []
        self.distinct_calls: list[tuple[str, dict]] = []
        self.distinct_values: list[object] = []

    async def create_index(self, keys, **kwargs):
        self.index_calls.append((keys, kwargs))
        return kwargs.get("name", "index")

    async def distinct(self, field, query):
        self.distinct_calls.append((field, query))
        return self.distinct_values


class FakeDatabase:
    def __init__(self) -> None:
        self.collections = {
            name: FakeCollection()
            for name in (
                "tasks",
                "employees",
                "departments",
                "users",
                "department_task_directives",
                "audit_logs",
            )
        }

    def __getitem__(self, name: str):
        return self.collections[name]


@pytest.mark.asyncio
async def test_task_repository_uses_partial_unique_seed_key_index() -> None:
    database = FakeDatabase()

    await TaskRepository(database).ensure_indexes()

    assert database.collections["tasks"].index_calls[0] == (
        "seed_key",
        {
            "unique": True,
            "partialFilterExpression": {"seed_key": {"$exists": True}},
        },
    )
    assert not any(
        kwargs.get("name") == "directed_task_once_unique"
        for _, kwargs in database.collections["department_task_directives"].index_calls
    )


@pytest.mark.asyncio
async def test_list_directed_task_ids_filters_to_active_directive_statuses() -> None:
    database = FakeDatabase()
    task_id = ObjectId()
    directives = database.collections["department_task_directives"]
    directives.distinct_values = [task_id, "not-an-object-id"]

    result = await TaskRepository(database).list_directed_task_ids(ACTIVE_DIRECTIVE_STATUSES)

    assert result == {task_id}
    assert len(directives.distinct_calls) == 1
    field, query = directives.distinct_calls[0]
    assert field == "task_ids"
    assert set(query["status"]["$in"]) == ACTIVE_DIRECTIVE_STATUSES
