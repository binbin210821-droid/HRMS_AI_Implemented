from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import PyMongoError


class AiConversationRepository:
    """Stores only bounded, scope-bound tool context for follow-up questions."""

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self.collection = database["ai_conversations"]

    async def get_context(
        self, conversation_id: str, user_id: str, scope: ObjectId | None
    ) -> dict[str, Any] | None:
        try:
            document = await self.collection.find_one(
                {
                    "_id": conversation_id,
                    "user_id": _object_id_or_string(user_id),
                    "department_id": scope,
                }
            )
        except (PyMongoError, RuntimeError):
            return None
        if document is None:
            return None
        return {
            "tool_name": document.get("last_tool_name"),
            "arguments": document.get("last_tool_arguments") or {},
            "updated_at": document.get("updated_at"),
        }

    async def save_tool_context(
        self,
        conversation_id: str,
        user_id: str,
        scope: ObjectId | None,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        now = datetime.now(timezone.utc)
        try:
            await self.collection.update_one(
                {"_id": conversation_id, "user_id": _object_id_or_string(user_id)},
                {
                    "$set": {
                        "department_id": scope,
                        "last_tool_name": tool_name,
                        "last_tool_arguments": arguments,
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "created_at": now,
                    },
                },
                upsert=True,
            )
        except (PyMongoError, RuntimeError):
            # Conversation continuity must never make the data tool unavailable.
            return


def _object_id_or_string(value: str) -> ObjectId | str:
    try:
        return ObjectId(value)
    except Exception:
        return value


__all__ = ["AiConversationRepository"]
