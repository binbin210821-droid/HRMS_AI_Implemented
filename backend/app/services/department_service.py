from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.pagination import Page
from app.core.time import BusinessClock
from app.models.department import (
    DepartmentCreate,
    DepartmentDocument,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.repositories.department_repository import DepartmentRepository


def parse_object_id(value: str, label: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{label} không hợp lệ"
        ) from None


class DepartmentService:
    def __init__(self, repository: DepartmentRepository, clock: BusinessClock | None = None) -> None:
        self.repository = repository
        self._clock = clock or BusinessClock()

    @staticmethod
    def _response(document: DepartmentDocument) -> DepartmentResponse:
        return DepartmentResponse(
            id=str(document.id),
            name=document.name,
            code=document.code,
            specialty=document.specialty,
            description=document.description,
            is_active=document.is_active,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    async def list(self, scope: ObjectId | None) -> list[DepartmentResponse]:
        return [self._response(document) for document in await self.repository.find_many(scope)]

    async def list_page(
        self, scope: ObjectId | None, offset: int, limit: int
    ) -> Page[DepartmentResponse]:
        page = await self.repository.find_many_page(scope, offset, limit)
        return Page(items=[self._response(document) for document in page.items], total=page.total)

    async def list_page_v1(
        self, scope: ObjectId | None, page: int, page_size: int
    ) -> Page[DepartmentResponse]:
        result = await self.repository.find_many_page_v1(scope, page, page_size)
        return Page(items=[self._response(document) for document in result.items], total=result.total)

    async def get(self, department_id: str, scope: ObjectId | None) -> DepartmentResponse:
        object_id = parse_object_id(department_id, "Mã phòng ban")
        if scope is not None and object_id != scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Ngoài phạm vi phòng ban"
            )
        document = await self.repository.find_by_id(object_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
            )
        return self._response(document)

    async def create(self, request: DepartmentCreate) -> DepartmentResponse:
        now = self._clock.now()
        document = {
            "_id": ObjectId(),
            "name": request.name.strip(),
            "code": request.code.strip().upper(),
            "specialty": request.specialty.strip() if request.specialty else None,
            "description": request.description.strip() if request.description else None,
            "is_active": request.is_active,
            "created_at": now,
            "updated_at": now,
        }
        try:
            created = await self.repository.insert(document)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Mã phòng ban đã tồn tại"
            ) from None
        return self._response(created)

    async def update(self, department_id: str, request: DepartmentUpdate) -> DepartmentResponse:
        object_id = parse_object_id(department_id, "Mã phòng ban")
        if await self.repository.find_by_id(object_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
            )
        values = request.model_dump(exclude_unset=True)
        if "name" in values:
            values["name"] = values["name"].strip()
        if "code" in values:
            values["code"] = values["code"].strip().upper()
        if "specialty" in values and values["specialty"] is not None:
            values["specialty"] = values["specialty"].strip() or None
        if values.get("description"):
            values["description"] = values["description"].strip()
        values["updated_at"] = self._clock.now()
        try:
            updated = await self.repository.update(object_id, values)
        except DuplicateKeyError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Mã phòng ban đã tồn tại"
            ) from None
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
            )
        return self._response(updated)

    async def delete(self, department_id: str) -> None:
        object_id = parse_object_id(department_id, "Mã phòng ban")
        if await self.repository.find_by_id(object_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phòng ban"
            )
        if await self.repository.count_employees(object_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Không thể xóa phòng ban đang có nhân viên",
            )
        await self.repository.delete(object_id)


__all__ = ["DepartmentService", "parse_object_id"]
