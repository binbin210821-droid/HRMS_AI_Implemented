from __future__ import annotations

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class KnowledgeChunk(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    document_id: str = Field(min_length=1, max_length=200)
    chunk_id: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=12000)
    department_id: ObjectId | None = None
    embedding: list[float] = Field(min_length=1)


class RetrievedKnowledge(BaseModel):
    chunk_id: str
    content: str
    score: float
    document_id: str


__all__ = ["KnowledgeChunk", "RetrievedKnowledge"]
