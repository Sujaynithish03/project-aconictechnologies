"""Chat request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.message import MessageRole


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    # Omit to search across every ready document the user owns.
    document_id: uuid.UUID | None = None


class SourceChunk(BaseModel):
    """A retrieved passage cited in an answer."""

    document_id: uuid.UUID
    document_name: str
    chunk_index: int
    snippet: str
    similarity: float


class AskResponse(BaseModel):
    message_id: uuid.UUID
    question: str
    answer: str
    sources: list[SourceChunk]
    created_at: datetime


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    document_id: uuid.UUID | None
    sources: list[SourceChunk] | None
    created_at: datetime


class HistoryResponse(BaseModel):
    messages: list[MessageRead]
    total: int
