"""Document response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocumentStatus


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    file_type: str
    size_bytes: int
    status: DocumentStatus
    error_message: str | None
    char_count: int
    chunk_count: int
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentRead]
    total: int


class DeleteResponse(BaseModel):
    detail: str
