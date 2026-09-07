from datetime import datetime

import pytest

from app.services.health_service import HealthService


class AvailableDatabase:
    async def is_database_available(self) -> bool:
        return True


class UnavailableDatabase:
    async def is_database_available(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_health_service_returns_healthy_response() -> None:
    response = await HealthService(AvailableDatabase()).check()

    assert response.status == "healthy"
    assert isinstance(response.timestamp, datetime)


@pytest.mark.asyncio
async def test_health_service_rejects_unavailable_database() -> None:
    with pytest.raises(Exception) as error:
        await HealthService(UnavailableDatabase()).check()

    assert error.value.status_code == 503
