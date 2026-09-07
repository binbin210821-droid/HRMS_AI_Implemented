from fastapi import APIRouter, Depends

from app.models.health import HealthResponse
from app.repositories.health_repository import HealthRepository
from app.services.health_service import HealthService

router = APIRouter(prefix="/api", tags=["Health"])


def get_health_service() -> HealthService:
    return HealthService(HealthRepository())


@router.get("/health", response_model=HealthResponse, summary="Kiểm tra trạng thái hệ thống")
async def health_check(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return await service.check()
