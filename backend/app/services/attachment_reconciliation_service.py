from datetime import datetime, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.time import BusinessClock
from app.infrastructure.evidence_storage import EvidenceStorage


class AttachmentReconciliationService:
    """Dọn object không còn được MongoDB tham chiếu sau khoảng an toàn."""

    COLLECTIONS = ("department_weekly_evaluations", "task_execution_reports")
    MANAGED_PREFIXES = ("department-evaluations/", "demo/task-execution/")

    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        storage: EvidenceStorage,
        clock: BusinessClock | None = None,
    ) -> None:
        self.database = database
        self.storage = storage
        self._clock = clock or BusinessClock()

    async def cleanup_orphans(self, grace_period: timedelta = timedelta(hours=24)) -> dict[str, int]:
        now = self._clock.now()
        expired_sessions = await self.database["attachment_upload_sessions"].find(
            {
                "expires_at": {"$lt": now},
                "status": {"$in": ["pending", "uploaded"]},
            }
        ).to_list(None)
        expired_session_count = 0
        for session in expired_sessions:
            storage_key = session.get("generated_storage_key")
            if storage_key:
                try:
                    await self.storage.delete(storage_key)
                except Exception:
                    pass
            await self.database["attachment_upload_sessions"].update_one(
                {"_id": session.get("_id")},
                {"$set": {"status": "expired", "updated_at": now}},
            )
            expired_session_count += 1

        referenced: set[str] = set()
        for collection_name in self.COLLECTIONS:
            documents = await self.database[collection_name].find(
                {"attachments.storage_key": {"$exists": True}},
                {"attachments.storage_key": 1},
            ).to_list(None)
            referenced.update(
                attachment.get("storage_key")
                for document in documents
                for attachment in document.get("attachments", [])
                if attachment.get("storage_key")
            )

        cutoff = now - grace_period
        deleted = 0
        skipped = 0
        for prefix in self.MANAGED_PREFIXES:
            objects = await self.storage.list_objects(prefix)
            for item in objects:
                key = item.get("key")
                last_modified = item.get("last_modified")
                if not isinstance(key, str) or key in referenced:
                    skipped += 1
                    continue
                if not isinstance(last_modified, datetime) or last_modified >= cutoff:
                    skipped += 1
                    continue
                await self.storage.delete(key)
                deleted += 1
        return {
            "deleted": deleted,
            "skipped": skipped,
            "referenced": len(referenced),
            "expired_sessions": expired_session_count,
        }


__all__ = ["AttachmentReconciliationService"]
