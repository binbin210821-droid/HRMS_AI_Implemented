from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any, Protocol

import httpx
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import ValidationError
from pymongo.errors import PyMongoError

from app.core.config import Settings
from app.models.ai_rag import KnowledgeChunk, RetrievedKnowledge


class AiEmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class KnowledgeRepository(Protocol):
    async def insert_chunks(self, chunks: Iterable[KnowledgeChunk]) -> int: ...

    async def search(
        self, embedding: list[float], scope: ObjectId | None, limit: int
    ) -> list[RetrievedKnowledge]: ...


class CloudflareEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self.account_id = settings.cloudflare_account_id.strip()
        self.api_token = settings.cloudflare_api_token.strip()
        self.model = settings.ai_embedding_model
        self.timeout_seconds = settings.ai_timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.account_id and self.api_token and self.model)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.configured:
            raise AiEmbeddingError("Embedding chưa được cấu hình")
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/run/{self.model}"
        )
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    json={"text": texts},
                )
            if response.status_code >= 400:
                raise AiEmbeddingError("Cloudflare embedding trả về lỗi")
            payload = response.json()
        except AiEmbeddingError:
            raise
        except (httpx.HTTPError, TimeoutError, ValueError) as error:
            raise AiEmbeddingError("Không thể kết nối tới embedding") from error
        data = (payload.get("result") or {}).get("data")
        if not isinstance(data, list) or not all(isinstance(item, list) for item in data):
            raise AiEmbeddingError("Embedding trả về dữ liệu không hợp lệ")
        return [[float(value) for value in item] for item in data]


class KnowledgeChunkRepository:
    def __init__(
        self,
        database: AsyncIOMotorDatabase,
        vector_index_name: str,
        local_fallback_enabled: bool = False,
        local_fallback_max_documents: int = 2000,
    ) -> None:
        self.collection = database["ai_knowledge_chunks"]
        self.vector_index_name = vector_index_name
        self.local_fallback_enabled = local_fallback_enabled
        self.local_fallback_max_documents = max(1, local_fallback_max_documents)

    async def insert_chunks(self, chunks: Iterable[KnowledgeChunk]) -> int:
        documents = [chunk.model_dump(by_alias=True) for chunk in chunks]
        if not documents:
            return 0
        result = await self.collection.insert_many(documents)
        return len(result.inserted_ids)

    async def search(
        self, embedding: list[float], scope: ObjectId | None, limit: int
    ) -> list[RetrievedKnowledge]:
        filter_value: dict[str, Any] = {}
        if scope is not None:
            filter_value = {"department_id": {"$in": [None, scope]}}
        pipeline: list[dict[str, Any]] = [
            {
                "$vectorSearch": {
                    "index": self.vector_index_name,
                    "path": "embedding",
                    "queryVector": embedding,
                    "numCandidates": max(limit * 10, 20),
                    "limit": limit,
                    **({"filter": filter_value} if filter_value else {}),
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "chunk_id": 1,
                    "document_id": 1,
                    "content": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        try:
            documents = await self.collection.aggregate(pipeline).to_list(limit)
        except (PyMongoError, RuntimeError):
            # Local MongoDB does not implement Atlas $vectorSearch. The bounded
            # fallback is opt-in for development; production should use Atlas.
            if not self.local_fallback_enabled:
                return []
            documents = await self._local_similarity_search(embedding, filter_value)
        results: list[RetrievedKnowledge] = []
        for document in documents:
            try:
                results.append(RetrievedKnowledge.model_validate(document))
            except ValidationError:
                continue
        return results

    async def _local_similarity_search(
        self, embedding: list[float], filter_value: dict[str, Any]
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if filter_value:
            query = {
                "$or": [
                    {"department_id": None},
                    {"department_id": filter_value["department_id"]["$in"][1]},
                ]
            }
        documents = await self.collection.find(
            query,
            {"_id": 0, "chunk_id": 1, "document_id": 1, "content": 1, "embedding": 1},
        ).limit(self.local_fallback_max_documents).to_list(None)
        scored: list[dict[str, Any]] = []
        for document in documents:
            vector = document.get("embedding")
            if not isinstance(vector, list):
                continue
            score = _cosine_similarity(embedding, vector)
            if score is None:
                continue
            scored.append({**document, "score": score})
        return sorted(scored, key=lambda item: item["score"], reverse=True)

    async def create_vector_index(self, dimensions: int = 1024) -> str:
        """Create the Atlas index explicitly; never run this during request handling."""

        definition = {
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": dimensions,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "department_id"},
            ]
        }
        result = await self.collection.create_search_index(
            {"name": self.vector_index_name, "definition": definition}
        )
        return str(result)


def _cosine_similarity(left: list[float], right: list[Any]) -> float | None:
    if len(left) != len(right) or not left:
        return None
    try:
        right_values = [float(value) for value in right]
        numerator = sum(a * b for a, b in zip(left, right_values, strict=True))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right_values))
    except (TypeError, ValueError):
        return None
    if left_norm == 0 or right_norm == 0:
        return None
    return numerator / (left_norm * right_norm)


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 160) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []
    if max_chars <= 0 or overlap < 0 or overlap >= max_chars:
        raise ValueError("Kích thước chunk không hợp lệ")
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + max_chars)
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = end - overlap
    return chunks


class RagService:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        repository: KnowledgeRepository,
        enabled: bool,
        top_k: int,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.repository = repository
        self.enabled = enabled
        self.top_k = max(1, top_k)

    async def index_document(
        self,
        document_id: str,
        text: str,
        department_id: ObjectId | None = None,
    ) -> int:
        """Chunk and embed one approved knowledge document before vector storage."""

        chunks = chunk_text(text)
        if not chunks:
            return 0
        vectors = await self.embedding_provider.embed(chunks)
        if len(vectors) != len(chunks):
            raise AiEmbeddingError("Số vector embedding không khớp số chunk")
        documents = [
            KnowledgeChunk(
                document_id=document_id,
                chunk_id=f"{document_id}:{index}",
                content=content,
                department_id=department_id,
                embedding=vector,
            )
            for index, (content, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        return await self.repository.insert_chunks(documents)

    async def retrieve(self, question: str, scope: ObjectId | None) -> list[RetrievedKnowledge]:
        if not self.enabled or not question.strip():
            return []
        try:
            vectors = await self.embedding_provider.embed([question[:8000]])
            if not vectors:
                return []
            return await self.repository.search(vectors[0], scope, self.top_k)
        except (AiEmbeddingError, PyMongoError, RuntimeError):
            return []

    @staticmethod
    def prompt_context(results: list[RetrievedKnowledge]) -> str:
        if not results:
            return "Chưa có tài liệu chính sách phù hợp trong kho tri thức."
        return "\n".join(
            f"- Tài liệu {result.document_id}: {result.content}"
            for result in results
        )


__all__ = [
    "AiEmbeddingError",
    "CloudflareEmbeddingProvider",
    "EmbeddingProvider",
    "KnowledgeChunkRepository",
    "KnowledgeRepository",
    "RagService",
    "chunk_text",
]
