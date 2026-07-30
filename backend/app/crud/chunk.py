"""Chunk persistence and vector similarity search."""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk plus its similarity score and owning document name."""

    document_id: uuid.UUID
    document_name: str
    chunk_index: int
    content: str
    similarity: float


def bulk_create(
    db: Session,
    *,
    document_id: uuid.UUID,
    contents: list[str],
    embeddings: list[list[float]],
) -> int:
    if len(contents) != len(embeddings):
        raise ValueError("contents and embeddings must be the same length")

    db.add_all(
        [
            DocumentChunk(
                document_id=document_id,
                chunk_index=index,
                content=content,
                embedding=embedding,
            )
            for index, (content, embedding) in enumerate(zip(contents, embeddings))
        ]
    )
    db.commit()
    return len(contents)


def delete_for_document(db: Session, *, document_id: uuid.UUID) -> None:
    """Clear existing chunks so a re-ingest never leaves duplicates behind."""
    db.execute(
        sa_delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    db.commit()


def search(
    db: Session,
    *,
    user_id: uuid.UUID,
    query_embedding: list[float],
    top_k: int,
    document_id: uuid.UUID | None = None,
) -> list[RetrievedChunk]:
    """Return the ``top_k`` most similar chunks the user is allowed to see.

    Uses pgvector's cosine distance operator (``<=>``); similarity is
    ``1 - distance`` so higher is better.
    """
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)

    statement = (
        select(
            DocumentChunk.document_id,
            Document.filename,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            distance.label("distance"),
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.user_id == user_id,
            Document.status == DocumentStatus.READY,
        )
        .order_by(distance)
        .limit(top_k)
    )
    if document_id is not None:
        statement = statement.where(Document.id == document_id)

    return [
        RetrievedChunk(
            document_id=row.document_id,
            document_name=row.filename,
            chunk_index=row.chunk_index,
            content=row.content,
            similarity=round(1.0 - float(row.distance), 4),
        )
        for row in db.execute(statement).all()
    ]
