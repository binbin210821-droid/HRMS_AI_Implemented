from bson import ObjectId
from fastapi import HTTPException, status

from app.core.time import BusinessClock
from app.models.threshold import (
    ThresholdConfigCreate,
    ThresholdConfigDocument,
    ThresholdConfigResponse,
    ThresholdConfigStatus,
)
from app.repositories.threshold_repository import ThresholdConfigRepository
from app.services.department_service import parse_object_id


class ThresholdConfigService:
    def __init__(self, repository: ThresholdConfigRepository, clock: BusinessClock | None = None) -> None:
        self.repository = repository
        self._clock = clock or BusinessClock()

    @staticmethod
    def _response(document: ThresholdConfigDocument) -> ThresholdConfigResponse:
        return ThresholdConfigResponse(
            id=str(document.id),
            department_id=str(document.department_id) if document.department_id else None,
            consecutive_days=document.consecutive_days,
            quality_drop_percent=document.quality_drop_percent,
            status=document.status,
            proposed_by=str(document.proposed_by),
            approved_by=str(document.approved_by) if document.approved_by else None,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    async def list(self, scope: ObjectId | None) -> list[ThresholdConfigResponse]:
        await self.repository.ensure_indexes()
        documents = await self.repository.find_many(scope)
        return [self._response(document) for document in documents]

    async def propose(
        self, request: ThresholdConfigCreate, scope: ObjectId | None, proposed_by: str
    ) -> ThresholdConfigResponse:
        await self.repository.ensure_indexes()
        if scope is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lãnh đạo không đề xuất cấu hình ngưỡng",
            )
        now = self._clock.now()
        document = {
            "_id": ObjectId(),
            "department_id": scope,
            "consecutive_days": request.consecutive_days,
            "quality_drop_percent": request.quality_drop_percent,
            "status": ThresholdConfigStatus.PROPOSED.value,
            "proposed_by": parse_object_id(proposed_by, "Mã người đề xuất"),
            "approved_by": None,
            "created_at": now,
            "updated_at": now,
        }
        created = await self.repository.insert(document)
        return self._response(created)

    async def approve(self, config_id: str, approved_by: str) -> ThresholdConfigResponse:
        await self.repository.ensure_indexes()
        object_id = parse_object_id(config_id, "Mã cấu hình ngưỡng")
        config = await self.repository.find_by_id(object_id)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cấu hình ngưỡng"
            )
        if config.status == ThresholdConfigStatus.APPROVED:
            return self._response(config)
        updated = await self.repository.approve(
            object_id,
            parse_object_id(approved_by, "Mã người duyệt"),
            self._clock.now(),
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cấu hình ngưỡng"
            )
        return self._response(updated)


__all__ = ["ThresholdConfigService"]
