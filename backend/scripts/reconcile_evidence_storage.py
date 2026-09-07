"""Dọn object minh chứng mồ côi; nên chạy định kỳ ngoài tiến trình API."""

import asyncio
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.infrastructure.evidence_storage import create_evidence_storage
from app.services.attachment_reconciliation_service import AttachmentReconciliationService


async def main() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri)
    try:
        service = AttachmentReconciliationService(
            client[settings.database_name], create_evidence_storage(settings)
        )
        print(await service.cleanup_orphans())
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
