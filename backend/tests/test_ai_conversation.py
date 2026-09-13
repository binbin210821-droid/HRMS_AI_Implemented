from collections.abc import AsyncIterator
from typing import Any

import pytest
from bson import ObjectId

from app.models.user import CurrentUser, UserRole
from app.repositories.ai_conversation_repository import AiConversationRepository
from app.services.ai_chat_orchestrator import AiChatOrchestrator


class ConversationCollectionFake:
    def __init__(self, document: dict[str, Any] | None = None) -> None:
        self.document = document
        self.find_filter: dict[str, Any] | None = None
        self.update_call: tuple[dict[str, Any], dict[str, Any]] | None = None

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        self.find_filter = query
        return self.document

    async def update_one(
        self, query: dict[str, Any], update: dict[str, Any], *, upsert: bool
    ) -> None:
        self.update_call = (query, update)


class ConversationDatabaseFake:
    def __init__(self, collection: ConversationCollectionFake) -> None:
        self.collection = collection

    def __getitem__(self, _name: str) -> ConversationCollectionFake:
        return self.collection


def _manager(department_id: str) -> CurrentUser:
    return CurrentUser(
        user_id="manager-1",
        username="manager",
        full_name="Quản lý",
        role=UserRole.MANAGER,
        department_id=department_id,
    )


@pytest.mark.asyncio
async def test_conversation_context_is_bound_to_user_and_scope() -> None:
    department_id = ObjectId()
    collection = ConversationCollectionFake(
        {
            "last_tool_name": "get_performance_trend",
            "last_tool_arguments": {"date_from": "2026-09-01"},
        }
    )
    repository = AiConversationRepository(ConversationDatabaseFake(collection))

    context = await repository.get_context("conversation-1", "manager-1", department_id)

    assert context is not None
    assert collection.find_filter == {
        "_id": "conversation-1",
        "user_id": "manager-1",
        "department_id": department_id,
    }

    await repository.get_context("conversation-1", "manager-1", ObjectId())
    assert collection.find_filter["department_id"] != department_id


@pytest.mark.asyncio
async def test_conversation_context_stores_bounded_tool_arguments_only() -> None:
    collection = ConversationCollectionFake()
    repository = AiConversationRepository(ConversationDatabaseFake(collection))
    scope = ObjectId()

    await repository.save_tool_context(
        "conversation-1",
        "manager-1",
        scope,
        "get_performance_trend",
        {"employee_name": "Nguyễn An", "date_from": "2026-09-01"},
    )

    assert collection.update_call is not None
    query, update = collection.update_call
    assert query == {"_id": "conversation-1", "user_id": "manager-1"}
    assert update["$set"]["last_tool_arguments"]["employee_name"] == "Nguyễn An"
    assert "prompt" not in str(update).casefold()
    assert "output" not in str(update).casefold()


class FollowUpToolService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def read_data_from_context(self, context, current_user, scope, **kwargs):
        self.calls.append({"context": context, "scope": scope, **kwargs})
        return "executed", "get_performance_trend", {
            "co_du_lieu": True,
            "du_lieu": [{"Nhân viên": "Nguyễn An", "Điểm hiệu suất": 73.16}],
            "ky_du_lieu": {"từ ngày": "2026-09-01", "đến ngày": "2026-09-07"},
        }, "Đã đọc dữ liệu."

    async def read_data_from_message(self, *_args, **_kwargs):
        raise AssertionError("follow-up phải dùng context đã lưu")


class FollowUpChatService:
    async def stream_grounded_response(self, *_args, **_kwargs) -> AsyncIterator[str]:
        yield "Nguyên nhân chính là điểm chất lượng thấp."


@pytest.mark.asyncio
async def test_follow_up_reexecutes_the_stored_read_tool_instead_of_trusting_old_output() -> None:
    tool_service = FollowUpToolService()
    orchestrator = AiChatOrchestrator(FollowUpChatService(), tool_service)
    manager = _manager(str(ObjectId()))

    chunks = [
        chunk
        async for chunk in orchestrator.stream_response(
            "Vì sao?",
            ObjectId(manager.department_id),
            manager,
            conversation_id="conversation-1",
            conversation_context={
                "tool_name": "get_performance_trend",
                "arguments": {"employee_name": "Nguyễn An"},
            },
        )
    ]

    assert chunks == ["Nguyên nhân chính là điểm chất lượng thấp."]
    assert tool_service.calls[0]["conversation_id"] == "conversation-1"
    assert tool_service.calls[0]["scope"] == ObjectId(manager.department_id)
