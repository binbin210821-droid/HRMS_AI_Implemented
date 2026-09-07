from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.models.health import HealthResponse
from app.repositories.health_repository import HealthRepository


class HealthService:
    def __init__(self, repository: HealthRepository) -> None:
        self.repository = repository

    async def check(self) -> HealthResponse:
        if not await self.repository.is_database_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cơ sở dữ liệu chưa sẵn sàng",
            )
        return HealthResponse(status="healthy", timestamp=datetime.now(timezone.utc))
