import pytest
from bson import ObjectId

from scripts.seed_tasks_data import resolve_task_creators


class FakeUsers:
    def __init__(self, managers: dict[ObjectId, ObjectId], leadership: ObjectId) -> None:
        self.managers = managers
        self.leadership = leadership

    async def find_one(self, query, _projection, sort):
        assert sort == [("username", 1)]
        if query["role"] == "manager":
            manager_id = self.managers.get(query["department_id"])
            return {"_id": manager_id} if manager_id else None
        return {"_id": self.leadership}


class FakeDatabase:
    def __init__(self, users: FakeUsers) -> None:
        self.users = users

    def __getitem__(self, collection_name: str):
        assert collection_name == "users"
        return self.users


@pytest.mark.asyncio
async def test_resolve_task_creators_prefers_department_manager_and_falls_back_to_leadership():
    department_with_manager = ObjectId()
    department_without_manager = ObjectId()
    manager_id = ObjectId()
    leadership_id = ObjectId()
    employees = [
        {"department_id": department_with_manager},
        {"department_id": department_without_manager},
    ]

    creators = await resolve_task_creators(
        FakeDatabase(FakeUsers({department_with_manager: manager_id}, leadership_id)), employees
    )

    assert creators == {
        department_with_manager: manager_id,
        department_without_manager: leadership_id,
    }
