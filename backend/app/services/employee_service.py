from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.pagination import Page
from app.core.time import BusinessClock
from app.models.employee import EmployeeCreate, EmployeeDocument, EmployeeResponse, EmployeeUpdate
from app.repositories.employee_repository import EmployeeRepository
from app.services.department_service import parse_object_id


class EmployeeService:
    def __init__(self, repository: EmployeeRepository, clock: BusinessClock | None = None) -> None:
        self.repository = repository
        self._clock = clock or BusinessClock()

    @staticmethod
    def _response(document: EmployeeDocument) -> EmployeeResponse:
        return EmployeeResponse(
            id=str(document.id),
            employee_code=document.employee_code,
            full_name=document.full_name,
            email=document.email,
            phone=document.phone,
            position=document.position,
            skills=document.skills,
            department_id=str(document.department_id),
            is_active=document.is_active,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    @staticmethod
    def _enforce_scope(department_id: ObjectId, scope: ObjectId | None) -> None:
        if scope is not None and department_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Ngoài phạm vi phòng ban"
            )

    async def list(
        self, scope: ObjectId | None, department_id: str | None = None
    ) -> list[EmployeeResponse]:
        requested_department = (
            parse_object_id(department_id, "Mã phòng ban") if department_id else None
        )
        documents = await self.repository.find_many(scope, requested_department)
        return [self._response(document) for document in documents]

    async def list_page(
        self,
        scope: ObjectId | None,
        department_id: str | None,
        offset: int,
        limit: int,
    ) -> Page[EmployeeResponse]:
        requested_department = (
            parse_object_id(department_id, "Mã phòng ban") if department_id else None
        )
        page = await self.repository.find_many_page(
            scope, requested_department, offset, limit
        )
        return Page(items=[self._response(document) for document in page.items], total=page.total)

    async def list_page_v1(
        self,
        scope: ObjectId | None,
        department_id: str | None,
        is_active: bool | None,
        sort_stage: dict[str, int],
        page: int,
        page_size: int,
    ) -> Page[EmployeeResponse]:
        requested_department = (
            parse_object_id(department_id, "Mã phòng ban") if department_id else None
        )
        result = await self.repository.find_many_page_v1(
            scope, requested_department, is_active, sort_stage, page, page_size
        )
        return Page(items=[self._response(document) for document in result.items], total=result.total)

    async def get(self, employee_id: str, scope: ObjectId | None) -> EmployeeResponse:
        object_id = parse_object_id(employee_id, "Mã nhân viên")
        document = await self.repository.find_by_id(object_id, scope)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên"
            )
        return self._response(document)

    async def create(self, request: EmployeeCreate, scope: ObjectId | None) -> EmployeeResponse:
        department_id = parse_object_id(request.department_id, "Mã phòng ban")
        self._enforce_scope(department_id, scope)
        if not await self.repository.department_exists(department_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
            )
        now = self._clock.now()
        document = {
            "_id": ObjectId(),
            "employee_code": request.employee_code.strip().upper(),
            "full_name": request.full_name.strip(),
            "email": request.email.strip() if request.email else None,
            "phone": request.phone.strip() if request.phone else None,
            "position": request.position.strip(),
            "skills": list(
                dict.fromkeys(item.strip().casefold() for item in request.skills if item.strip())
            ),
            "department_id": department_id,
            "is_active": request.is_active,
            "created_at": now,
            "updated_at": now,
        }
        try:
            created = await self.repository.insert(document)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Mã nhân viên đã tồn tại"
            ) from None
        return self._response(created)

    async def update(
        self, employee_id: str, request: EmployeeUpdate, scope: ObjectId | None
    ) -> EmployeeResponse:
        object_id = parse_object_id(employee_id, "Mã nhân viên")
        existing = await self.repository.find_by_id(object_id, scope)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên"
            )

        values = request.model_dump(exclude_unset=True)
        if "department_id" in values:
            if values["department_id"] is None:
                raise HTTPException(status_code=422, detail="Nhân viên phải thuộc một phòng ban")
            department_id = parse_object_id(values["department_id"], "Mã phòng ban")
            self._enforce_scope(department_id, scope)
            if not await self.repository.department_exists(department_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
                )
            values["department_id"] = department_id
        for field in ("employee_code", "full_name", "email", "phone", "position"):
            if field in values and isinstance(values[field], str):
                values[field] = values[field].strip()
        if "skills" in values:
            values["skills"] = list(
                dict.fromkeys(
                    item.strip().casefold()
                    for item in values["skills"]
                    if item and item.strip()
                )
            )
        if "employee_code" in values:
            values["employee_code"] = values["employee_code"].upper()
        values["updated_at"] = self._clock.now()
        try:
            updated = await self.repository.update(object_id, values, scope)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Mã nhân viên đã tồn tại"
            ) from None
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên"
            )
        return self._response(updated)

    async def delete(self, employee_id: str, scope: ObjectId | None) -> None:
        object_id = parse_object_id(employee_id, "Mã nhân viên")
        if await self.repository.find_by_id(object_id, scope) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nhân viên"
            )
        await self.repository.delete(object_id, scope)
