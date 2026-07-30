"""A chunk of document text plus its embedding vector."""

import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base_class import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentChunk(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Dimensionality is fixed at table-creation time. Changing
    # EMBEDDING_DIMENSIONS on an existing database requires a migration.
    embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk doc={self.document_id} #{self.chunk_index}>"
