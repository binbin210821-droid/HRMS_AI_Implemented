import pytest

from app.repositories.task_repository import TaskRepository


class FakeCollection:
    def __init__(self) -> None:
        self.index_calls: list[tuple[object, dict]] = []

    async def create_index(self, keys, **kwargs):
        self.index_calls.append((keys, kwargs))
        return kwargs.get("name", "index")


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
