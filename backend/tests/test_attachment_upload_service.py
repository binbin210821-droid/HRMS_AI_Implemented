import hashlib
from datetime import date, datetime, timezone

import pytest
from bson import ObjectId

from app.core.config import Settings
from app.infrastructure.malware_scanner import ScanResult
from app.models.attachment import CreateUploadSessionRequest, UploadSessionDocument
from app.models.user import CurrentUser, UserRole
from app.services.attachment_upload_service import AttachmentUploadService
from tests.time_fixtures import FixedBusinessClock


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.keys_by_url = {}

    async def ensure_browser_upload_config(self):
        return None

    async def create_upload_url(self, key, content_type, checksum, expires_in):
        url = f"https://storage.test/upload/{len(self.keys_by_url)}"
        self.keys_by_url[url] = key
        return url

    async def head_object(self, key):
        content = self.objects.get(key)
        if content is None:
            return None
        return {
            "size": len(content),
            "content_type": "application/pdf",
            "checksum": hashlib.sha256(content).hexdigest(),
        }

    async def read_bytes(self, key):
        return self.objects.get(key)

    async def delete(self, key):
        self.objects.pop(key, None)


class FakeRepository:
    def __init__(self):
        self.documents = {}
        self.last = None

    async def ensure_indexes(self):
        return None

    async def department_is_active(self, department_id):
        return True

    async def task_belongs_to_department(self, task_id, department_id):
        return True

    async def insert(self, values):
        self.last = UploadSessionDocument.model_validate(values)
        self.documents[self.last.id] = self.last
        return self.last

    async def find_by_id(self, session_id):
        return self.documents.get(session_id)

    async def update_status(self, session_id, status, updated_at):
        current = self.documents[session_id]
        values = current.model_dump(by_alias=True)
        values.update({"status": status, "updated_at": updated_at})
        self.documents[session_id] = UploadSessionDocument.model_validate(values)
        return self.documents[session_id]

    async def mark_committed(self, session_ids, now):
        for session_id in session_ids:
            await self.update_status(session_id, "committed", now)

    async def mark_failed(self, session_ids, now):
        for session_id in session_ids:
            if session_id in self.documents:
                await self.update_status(session_id, "failed", now)

    async def find_for_owner(self, session_ids, owner_id):
        return [
            document
            for session_id in session_ids
            if (document := self.documents.get(session_id)) is not None
            and document.owner_id == owner_id
        ]


def settings():
    return Settings(
        _env_file=None,
        storage_bucket="test",
        storage_direct_upload_enabled=True,
        storage_allowed_content_types={"application/pdf"},
    )


def leadership():
    return CurrentUser(
        user_id="leader-1",
        username="leader",
        full_name="Lãnh đạo",
        role=UserRole.LEADERSHIP,
        department_id=None,
    )


def manager(department_id: ObjectId) -> CurrentUser:
    return CurrentUser(
        user_id="manager-1",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id=str(department_id),
    )


def department_request(department_id: ObjectId, content: bytes = b"task-file"):
    return CreateUploadSessionRequest(
        purpose="task_execution_report",
        department_id=str(department_id),
        task_id=str(ObjectId()),
        work_date=date(2026, 9, 6),
        file_name="bao-cao.pdf",
        content_type="application/pdf",
        file_size=len(content),
        checksum=hashlib.sha256(content).hexdigest(),
    )


@pytest.mark.asyncio
async def test_direct_upload_complete_verifies_object_and_marks_uploaded():
    repository = FakeRepository()
    storage = FakeStorage()
    content = b"%PDF-test"
    service = AttachmentUploadService(
        repository,
        storage,
        settings(),
        clock=FixedBusinessClock(datetime(2026, 9, 6, tzinfo=timezone.utc)),
    )
    request = CreateUploadSessionRequest(
        purpose="department_evaluation",
        department_id=str(ObjectId()),
        week_start=date(2026, 8, 31),
        file_name="huong-dan.pdf",
        content_type="application/pdf",
        file_size=len(content),
        checksum=hashlib.sha256(content).hexdigest(),
    )

    created = await service.create(request, leadership(), None)
    storage.objects[repository.last.generated_storage_key] = content

    completed = await service.complete(created.id, leadership())

    assert completed.status == "uploaded"
    assert repository.documents[created.id].status == "uploaded"


@pytest.mark.asyncio
async def test_direct_upload_rejects_checksum_mismatch_without_metadata():
    repository = FakeRepository()
    storage = FakeStorage()
    service = AttachmentUploadService(
        repository,
        storage,
        settings(),
        clock=FixedBusinessClock(datetime(2026, 9, 6, tzinfo=timezone.utc)),
    )
    request = CreateUploadSessionRequest(
        purpose="department_evaluation",
        department_id=str(ObjectId()),
        week_start=date(2026, 8, 31),
        file_name="huong-dan.pdf",
        content_type="application/pdf",
        file_size=9,
        checksum="a" * 64,
    )
    created = await service.create(request, leadership(), None)
    storage.objects[repository.last.generated_storage_key] = b"wrong-file"

    with pytest.raises(Exception) as error:
        await service.complete(created.id, leadership())

    assert getattr(error.value, "status_code", None) == 422
    assert repository.documents[created.id].status == "failed"


@pytest.mark.asyncio
async def test_direct_upload_checks_owner_and_manager_scope():
    repository = FakeRepository()
    storage = FakeStorage()
    department_id = ObjectId()
    service = AttachmentUploadService(repository, storage, settings())

    with pytest.raises(Exception) as scope_error:
        await service.create(department_request(department_id), manager(department_id), ObjectId())
    assert getattr(scope_error.value, "status_code", None) == 403

    created = await service.create(department_request(department_id), manager(department_id), department_id)
    with pytest.raises(Exception) as owner_error:
        await service._owned_session(created.id, "another-owner")
    assert getattr(owner_error.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_direct_upload_commit_marks_uploaded_session_committed():
    repository = FakeRepository()
    service = AttachmentUploadService(repository, FakeStorage(), settings())
    department_id = ObjectId()
    created = await service.create(department_request(department_id), manager(department_id), department_id)

    await repository.update_status(created.id, "uploaded", datetime.now(timezone.utc))
    await service.commit([created.id])

    assert repository.documents[created.id].status == "committed"


@pytest.mark.asyncio
async def test_direct_upload_cancel_and_discard_remove_objects_and_update_status():
    repository = FakeRepository()
    storage = FakeStorage()
    service = AttachmentUploadService(repository, storage, settings())
    department_id = ObjectId()
    owner = manager(department_id)
    cancelled = await service.create(department_request(department_id), owner, department_id)
    discarded = await service.create(department_request(department_id), owner, department_id)
    storage.objects[repository.documents[cancelled.id].generated_storage_key] = b"cancelled"
    storage.objects[repository.documents[discarded.id].generated_storage_key] = b"discarded"

    await service.cancel(cancelled.id, owner)
    await service.discard([discarded.id], owner.user_id)

    assert repository.documents[cancelled.id].status == "cancelled"
    assert repository.documents[discarded.id].status == "failed"
    assert storage.objects == {}


@pytest.mark.asyncio
async def test_direct_upload_rejects_malware_scan_and_marks_failed():
    class FailingScanner:
        async def scan(self, _content: bytes) -> ScanResult:
            return ScanResult(clean=False, reason="test malware")

    repository = FakeRepository()
    storage = FakeStorage()
    content = b"malware-test"
    department_id = ObjectId()
    service = AttachmentUploadService(
        repository,
        storage,
        settings(),
        scanner=FailingScanner(),
    )
    created = await service.create(
        department_request(department_id, content), manager(department_id), department_id
    )
    storage.objects[repository.documents[created.id].generated_storage_key] = content

    with pytest.raises(Exception) as error:
        await service.complete(created.id, manager(department_id))

    assert getattr(error.value, "status_code", None) == 422
    assert repository.documents[created.id].status == "failed"
