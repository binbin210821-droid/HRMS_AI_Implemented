from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.models.employee import EmployeeCreate, EmployeeDocument, EmployeeUpdate
from app.services.employee_service import EmployeeService


def make_employee(
    employee_id: ObjectId | None = None, department_id: ObjectId | None = None, code: str = "KD-001"
) -> EmployeeDocument:
    now = datetime.now(timezone.utc)
    return EmployeeDocument(
        _id=employee_id or ObjectId(),
        employee_code=code,
        full_name="Nguyễn Văn A",
        email="a@example.com",
        phone="0900000000",
        position="Chuyên viên",
        department_id=department_id or ObjectId(),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


class FakeEmployeeRepository:
    def __init__(self, documents: list[EmployeeDocument] | None = None) -> None:
        self.documents = {document.id: document for document in documents or []}
        self.departments: set[ObjectId] = set()
        self.duplicate_on_insert = False
        self.duplicate_on_update = False

    async def find_many(
        self, scope: ObjectId | None, department_id: ObjectId | None = None
    ) -> list[EmployeeDocument]:
        return [
            document
            for document in self.documents.values()
            if (scope is None or document.department_id == scope)
            and (
                scope is not None
                or department_id is None
                or document.department_id == department_id
            )
        ]

    async def find_by_id(
        self, employee_id: ObjectId, scope: ObjectId | None = None
    ) -> EmployeeDocument | None:
        document = self.documents.get(employee_id)
        if document is None or (scope is not None and document.department_id != scope):
            return None
        return document

    async def department_exists(self, department_id: ObjectId) -> bool:
        return department_id in self.departments

    async def insert(self, document: dict) -> EmployeeDocument:
        if self.duplicate_on_insert:
            raise DuplicateKeyError("duplicate employee")
        created = EmployeeDocument.model_validate(document)
        self.documents[created.id] = created
        return created

    async def update(
        self, employee_id: ObjectId, values: dict, scope: ObjectId | None = None
    ) -> EmployeeDocument | None:
        if self.duplicate_on_update:
            raise DuplicateKeyError("duplicate employee")
        current = self.documents[employee_id].model_dump(by_alias=True)
        current.update(values)
        updated = EmployeeDocument.model_validate(current)
        self.documents[employee_id] = updated
        return await self.find_by_id(employee_id, scope)

    async def delete(self, employee_id: ObjectId, scope: ObjectId | None = None) -> bool:
        if await self.find_by_id(employee_id, scope) is None:
            return False
        del self.documents[employee_id]
        return True


def employee_request(department_id: ObjectId, **values: str) -> EmployeeCreate:
    return EmployeeCreate(
        employee_code=values.get("employee_code", "nv-002"),
        full_name=values.get("full_name", "Trần Thị B"),
        email=values.get("email", "b@example.com"),
        phone=values.get("phone", "0911111111"),
        position=values.get("position", "Chuyên viên"),
        department_id=str(department_id),
    )


@pytest.mark.asyncio
async def test_manager_list_and_get_are_isolated_to_department() -> None:
    own_department = ObjectId()
    other_department = ObjectId()
    own = make_employee(department_id=own_department)
    other = make_employee(department_id=other_department, code="KT-001")
    repository = FakeEmployeeRepository([own, other])
    service = EmployeeService(repository)

    listed = await service.list(own_department, str(other_department))
    assert [employee.employee_code for employee in listed] == ["KD-001"]
    assert (await service.get(str(own.id), own_department)).employee_code == "KD-001"

    with pytest.raises(HTTPException) as hidden:
        await service.get(str(other.id), own_department)
    assert hidden.value.status_code == 404


@pytest.mark.asyncio
async def test_leadership_can_list_by_department_and_manager_cannot_create_outside_scope() -> None:
    own_department = ObjectId()
    other_department = ObjectId()
    repository = FakeEmployeeRepository()
    repository.departments.update({own_department, other_department})
    service = EmployeeService(repository)

    all_employees = await service.list(None)
    assert all_employees == []
    with pytest.raises(HTTPException) as forbidden:
        await service.create(employee_request(other_department), own_department)
    assert forbidden.value.status_code == 403

    created = await service.create(employee_request(own_department), own_department)
    assert created.employee_code == "NV-002"
    assert created.department_id == str(own_department)


@pytest.mark.asyncio
async def test_create_validates_department_and_duplicate_code() -> None:
    department_id = ObjectId()
    repository = FakeEmployeeRepository()
    service = EmployeeService(repository)
    request = employee_request(department_id)
    with pytest.raises(HTTPException) as missing_department:
        await service.create(request, None)
    assert missing_department.value.status_code == 404

    repository.departments.add(department_id)
    repository.duplicate_on_insert = True
    with pytest.raises(HTTPException) as duplicate:
        await service.create(request, None)
    assert duplicate.value.status_code == 409


@pytest.mark.asyncio
async def test_update_enforces_scope_and_normalizes_fields() -> None:
    own_department = ObjectId()
    other_department = ObjectId()
    employee = make_employee(department_id=own_department)
    repository = FakeEmployeeRepository([employee])
    repository.departments.update({own_department, other_department})
    service = EmployeeService(repository)

    updated = await service.update(
        str(employee.id),
        EmployeeUpdate(employee_code=" nv-009 ", full_name=" Trần C "),
        own_department,
    )
    assert updated.employee_code == "NV-009"
    assert updated.full_name == "Trần C"

    with pytest.raises(HTTPException) as forbidden:
        await service.update(
            str(employee.id), EmployeeUpdate(department_id=str(other_department)), own_department
        )
    assert forbidden.value.status_code == 403

    with pytest.raises(HTTPException) as invalid:
        await service.update(str(employee.id), EmployeeUpdate(department_id=None), own_department)
    assert invalid.value.status_code == 422

    with pytest.raises(HTTPException) as missing:
        await service.update(str(ObjectId()), EmployeeUpdate(full_name="Không có"), None)
    assert missing.value.status_code == 404


@pytest.mark.asyncio
async def test_update_maps_missing_department_and_duplicate_employee_code() -> None:
    department_id = ObjectId()
    missing_department = ObjectId()
    employee = make_employee(department_id=department_id)
    repository = FakeEmployeeRepository([employee])
    repository.departments.add(department_id)
    service = EmployeeService(repository)

    with pytest.raises(HTTPException) as missing:
        await service.update(
            str(employee.id), EmployeeUpdate(department_id=str(missing_department)), None
        )
    assert missing.value.status_code == 404

    repository.duplicate_on_update = True
    with pytest.raises(HTTPException) as duplicate:
        await service.update(str(employee.id), EmployeeUpdate(full_name="Tên mới"), None)
    assert duplicate.value.status_code == 409


@pytest.mark.asyncio
async def test_delete_is_scoped_and_reports_missing_employee() -> None:
    own_department = ObjectId()
    other_department = ObjectId()
    employee = make_employee(department_id=own_department)
    repository = FakeEmployeeRepository([employee])
    service = EmployeeService(repository)

    with pytest.raises(HTTPException) as hidden:
        await service.delete(str(employee.id), other_department)
    assert hidden.value.status_code == 404

    await service.delete(str(employee.id), own_department)
    with pytest.raises(HTTPException) as missing:
        await service.delete(str(employee.id), own_department)
    assert missing.value.status_code == 404
