"""Aggregates every model onto ``Base.metadata`` for schema creation.

Import this module (never the individual models) before calling ``create_all``.
"""

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus
from app.models.message import Message, MessageRole
from app.models.user import User

__all__ = [
    "Base",
    "Document",
    "DocumentChunk",
    "DocumentStatus",
    "Message",
    "MessageRole",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "utcnow",
]
