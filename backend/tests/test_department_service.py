from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.models.department import DepartmentCreate, DepartmentDocument, DepartmentUpdate
from app.services.department_service import DepartmentService


def make_department(department_id: ObjectId | None = None, code: str = "KD") -> DepartmentDocument:
    now = datetime.now(timezone.utc)
    return DepartmentDocument(
        _id=department_id or ObjectId(),
        name="Kinh doanh",
        code=code,
        description="Phòng kinh doanh",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


class FakeDepartmentRepository:
    def __init__(self, document: DepartmentDocument | None = None) -> None:
        self.documents = {document.id: document} if document else {}
        self.employee_counts: dict[ObjectId, int] = {}
        self.return_none_on_update = False
        self.duplicate_on_insert = False
        self.duplicate_on_update = False

    async def find_many(self, scope: ObjectId | None) -> list[DepartmentDocument]:
        if scope is None:
            return list(self.documents.values())
        return [document for document in self.documents.values() if document.id == scope]

    async def find_by_id(self, department_id: ObjectId) -> DepartmentDocument | None:
        return self.documents.get(department_id)

    async def insert(self, document: dict) -> DepartmentDocument:
        if self.duplicate_on_insert:
            raise DuplicateKeyError("duplicate department")
        created = DepartmentDocument.model_validate(document)
        self.documents[created.id] = created
        return created

    async def update(self, department_id: ObjectId, values: dict) -> DepartmentDocument | None:
        if self.duplicate_on_update:
            raise DuplicateKeyError("duplicate department")
        if self.return_none_on_update:
            return None
        current = self.documents[department_id].model_dump(by_alias=True)
        current.update(values)
        updated = DepartmentDocument.model_validate(current)
        self.documents[department_id] = updated
        return updated

    async def count_employees(self, department_id: ObjectId) -> int:
        return self.employee_counts.get(department_id, 0)

    async def delete(self, department_id: ObjectId) -> bool:
        return self.documents.pop(department_id, None) is not None


@pytest.mark.asyncio
async def test_list_and_get_are_scoped_for_manager() -> None:
    own_id = ObjectId()
    other_id = ObjectId()
    repository = FakeDepartmentRepository(make_department(own_id))
    repository.documents[other_id] = make_department(other_id, "KT")
    service = DepartmentService(repository)

    scoped = await service.list(own_id)
    all_departments = await service.list(None)
    assert [department.code for department in scoped] == ["KD"]
    assert {department.code for department in all_departments} == {"KD", "KT"}

    with pytest.raises(HTTPException) as forbidden:
        await service.get(str(other_id), own_id)
    assert forbidden.value.status_code == 403


@pytest.mark.asyncio
async def test_get_rejects_invalid_or_missing_department() -> None:
    service = DepartmentService(FakeDepartmentRepository())

    with pytest.raises(HTTPException) as invalid:
        await service.get("not-an-object-id", None)
    assert invalid.value.status_code == 422

    with pytest.raises(HTTPException) as missing:
        await service.get(str(ObjectId()), None)
    assert missing.value.status_code == 404


@pytest.mark.asyncio
async def test_create_normalizes_fields_and_maps_duplicate() -> None:
    repository = FakeDepartmentRepository()
    service = DepartmentService(repository)
    created = await service.create(
        DepartmentCreate(name="  Kỹ thuật ", code=" kt ", description="  Nền tảng  ")
    )
    assert created.name == "Kỹ thuật"
    assert created.code == "KT"
    assert created.description == "Nền tảng"

    repository.duplicate_on_insert = True
    with pytest.raises(HTTPException) as duplicate:
        await service.create(DepartmentCreate(name="Khác", code="KH"))
    assert duplicate.value.status_code == 409


@pytest.mark.asyncio
async def test_update_handles_normalization_missing_duplicate_and_empty_result() -> None:
    department_id = ObjectId()
    repository = FakeDepartmentRepository(make_department(department_id))
    service = DepartmentService(repository)
    updated = await service.update(
        str(department_id), DepartmentUpdate(name="  Kinh doanh mới ", code=" kd ")
    )
    assert updated.name == "Kinh doanh mới"
    assert updated.code == "KD"

    repository.duplicate_on_update = True
    with pytest.raises(HTTPException) as duplicate:
        await service.update(str(department_id), DepartmentUpdate(code="XX"))
    assert duplicate.value.status_code == 409

    repository.duplicate_on_update = False
    repository.return_none_on_update = True
    with pytest.raises(HTTPException) as empty:
        await service.update(str(department_id), DepartmentUpdate(description="Mới"))
    assert empty.value.status_code == 404

    with pytest.raises(HTTPException) as missing:
        await service.update(str(ObjectId()), DepartmentUpdate(name="Không có"))
    assert missing.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_requires_existing_empty_department() -> None:
    department_id = ObjectId()
    repository = FakeDepartmentRepository(make_department(department_id))
    service = DepartmentService(repository)
    repository.employee_counts[department_id] = 1
    with pytest.raises(HTTPException) as occupied:
        await service.delete(str(department_id))
    assert occupied.value.status_code == 409

    repository.employee_counts[department_id] = 0
    await service.delete(str(department_id))
    assert department_id not in repository.documents

    with pytest.raises(HTTPException) as missing:
        await service.delete(str(department_id))
    assert missing.value.status_code == 404
