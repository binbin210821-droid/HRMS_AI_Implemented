from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.errors import PyMongoError


class AiAuditLogger:
    """Stores minimal AI governance evidence, never the full prompt/output."""

    def __init__(self, collection, provider: str = "unknown", model: str = "unknown") -> None:
        self.collection = collection
        self.provider = provider
        self.model = model

    async def record(
        self,
        *,
        actor_id: str | None,
        department_id: ObjectId | None,
        provider: str,
        model: str,
        request_type: str,
        input_text: str,
        output_text: str = "",
        status: str,
        tool_name: str | None = None,
        output_summary: dict[str, Any] | None = None,
    ) -> None:
        document = {
            "action": "ai_request",
            "user_id": _object_id_or_string(actor_id),
            "actor_id": _object_id_or_string(actor_id),
            "department_id": department_id,
            "provider": provider,
            "model": model,
            "request_type": request_type,
            "tool_name": tool_name,
            "input_summary": _text_summary(input_text),
            "output_summary": {
                **_text_summary(output_text),
                **(output_summary or {}),
            },
            "status": status,
            "created_at": datetime.now(timezone.utc),
        }
        try:
            await self.collection.insert_one(document)
        except (PyMongoError, RuntimeError):
            # Governance must not make the AI endpoint unavailable.
            return

    async def insert_audit_log(self, document: dict[str, Any]) -> None:
        """Adapter for the tool registry's generic audit writer contract."""

        try:
            await self.collection.insert_one(
                {
                    **document,
                    "provider": document.get("provider", self.provider),
                    "model": document.get("model", self.model),
                    "request_type": document.get("request_type", "tool_call"),
                    "created_at": datetime.now(timezone.utc),
                }
            )
        except (PyMongoError, RuntimeError):
            return


def _text_summary(value: str) -> dict[str, Any]:
    return {
        "length": len(value),
        "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
    }


def _object_id_or_string(value: str | None) -> ObjectId | str | None:
    if value is None:
        return None
    try:
        return ObjectId(value)
    except Exception:
        return value


__all__ = ["AiAuditLogger"]
