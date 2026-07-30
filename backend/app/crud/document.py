"""Document queries. Every read is scoped by ``user_id`` to enforce tenant isolation."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus


def create(
    db: Session,
    *,
    user_id: uuid.UUID,
    filename: str,
    file_type: str,
    size_bytes: int,
    raw_text: str,
) -> Document:
    document = Document(
        user_id=user_id,
        filename=filename,
        file_type=file_type,
        size_bytes=size_bytes,
        raw_text=raw_text,
        char_count=len(raw_text),
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_for_user(
    db: Session, *, document_id: uuid.UUID, user_id: uuid.UUID
) -> Document | None:
    """Scoping by user_id means another user's id simply reads as 'not found'."""
    return db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )


def list_for_user(
    db: Session, *, user_id: uuid.UUID, limit: int = 100, offset: int = 0
) -> tuple[list[Document], int]:
    total = (
        db.scalar(
            select(func.count(Document.id)).where(Document.user_id == user_id)
        )
        or 0
    )
    documents = list(
        db.scalars(
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return documents, total


def count_ready_for_user(db: Session, *, user_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count(Document.id)).where(
                Document.user_id == user_id,
                Document.status == DocumentStatus.READY,
            )
        )
        or 0
    )


def set_status(
    db: Session,
    *,
    document: Document,
    status: DocumentStatus,
    error_message: str | None = None,
    char_count: int | None = None,
    chunk_count: int | None = None,
) -> Document:
    document.status = status
    document.error_message = error_message
    if char_count is not None:
        document.char_count = char_count
    if chunk_count is not None:
        document.chunk_count = chunk_count
    db.commit()
    db.refresh(document)
    return document


def delete(db: Session, *, document: Document) -> None:
    db.delete(document)
    db.commit()
