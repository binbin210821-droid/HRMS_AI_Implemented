from typing import Any

import pytest
from bson import ObjectId

from app.ai.governance import AiAuditLogger


class CollectionSpy:
    def __init__(self) -> None:
        self.documents: list[dict[str, Any]] = []

    async def insert_one(self, document: dict[str, Any]) -> None:
        self.documents.append(document)


@pytest.mark.asyncio
async def test_ai_audit_stores_hashes_not_full_prompt_or_output() -> None:
    collection = CollectionSpy()
    logger = AiAuditLogger(collection)
    prompt = "Dữ liệu nhân sự rất nhạy cảm không được lưu nguyên văn"
    output = "Câu trả lời nội bộ cũng không được lưu nguyên văn"

    await logger.record(
        actor_id=str(ObjectId()),
        department_id=ObjectId(),
        provider="cloudflare",
        model="@cf/google/gemma-4-26b-a4b-it",
        request_type="chat",
        input_text=prompt,
        output_text=output,
        status="success",
    )

    document = collection.documents[0]
    serialized = str(document)
    assert document["action"] == "ai_request"
    assert document["provider"] == "cloudflare"
    assert document["request_type"] == "chat"
    assert document["input_summary"]["length"] == len(prompt)
    assert document["output_summary"]["length"] == len(output)
    assert prompt not in serialized
    assert output not in serialized

