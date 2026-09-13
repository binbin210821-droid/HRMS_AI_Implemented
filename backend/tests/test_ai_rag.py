from typing import Any

import pytest
from bson import ObjectId

from app.ai.rag import KnowledgeChunkRepository, RagService, chunk_text
from app.models.ai_rag import RetrievedKnowledge


def test_chunk_text_normalizes_and_overlaps_without_empty_chunks() -> None:
    chunks = chunk_text("  một   hai ba bốn năm sáu  ", max_chars=10, overlap=2)

    assert chunks
    assert all(chunk for chunk in chunks)
    assert "  " not in "".join(chunks)


@pytest.mark.asyncio
async def test_rag_disabled_does_not_call_embedding() -> None:
    class EmbeddingSpy:
        async def embed(self, _texts: list[str]) -> list[list[float]]:
            raise AssertionError("RAG tắt không được gọi embedding")

    class RepositorySpy:
        async def search(self, *_args: Any) -> list[RetrievedKnowledge]:
            raise AssertionError("RAG tắt không được truy vấn vector")

    service = RagService(EmbeddingSpy(), RepositorySpy(), enabled=False, top_k=4)

    assert await service.retrieve("chính sách nghỉ phép", ObjectId()) == []


@pytest.mark.asyncio
async def test_rag_retrieves_with_scope_and_builds_prompt_context() -> None:
    scope = ObjectId()
    received: dict[str, Any] = {}

    class Embedding:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            received["texts"] = texts
            return [[0.1, 0.2]]

    class Repository:
        async def search(self, vector: list[float], actual_scope: ObjectId, limit: int):
            received["search"] = (vector, actual_scope, limit)
            return [
                RetrievedKnowledge(
                    chunk_id="chunk-1",
                    document_id="leave-policy",
                    content="Nhân viên cần gửi đơn trước ngày nghỉ.",
                    score=0.91,
                )
            ]

    service = RagService(Embedding(), Repository(), enabled=True, top_k=3)
    results = await service.retrieve("quy trình nghỉ phép", scope)

    assert len(results) == 1
    assert received["search"] == ([0.1, 0.2], scope, 3)
    assert "Nhân viên cần gửi đơn" in service.prompt_context(results)


@pytest.mark.asyncio
async def test_rag_indexes_document_by_chunking_then_embedding() -> None:
    captured: dict[str, Any] = {}

    class Embedding:
        async def embed(self, texts: list[str]) -> list[list[float]]:
            captured["texts"] = texts
            return [[float(index)] for index, _ in enumerate(texts)]

    class Repository:
        async def insert_chunks(self, chunks) -> int:
            captured["chunks"] = list(chunks)
            return len(captured["chunks"])

        async def search(self, *_args: Any) -> list[RetrievedKnowledge]:
            return []

    service = RagService(Embedding(), Repository(), enabled=True, top_k=3)
    inserted = await service.index_document("leave-policy", "A" * 1300, ObjectId())

    assert inserted == len(captured["texts"]) == len(captured["chunks"])
    assert captured["chunks"][0].chunk_id == "leave-policy:0"
    assert captured["chunks"][0].document_id == "leave-policy"


@pytest.mark.asyncio
async def test_vector_repository_returns_empty_when_local_mongo_lacks_vector_index() -> None:
    class Collection:
        def aggregate(self, _pipeline):
            raise RuntimeError("$vectorSearch chưa được hỗ trợ")

    class Database:
        def __getitem__(self, _name: str):
            return Collection()

    repository = KnowledgeChunkRepository(Database(), "workmind-index")

    assert await repository.search([0.1], None, 4) == []
