"""Chat message persistence."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.message import Message, MessageRole


def create(
    db: Session,
    *,
    user_id: uuid.UUID,
    role: MessageRole,
    content: str,
    document_id: uuid.UUID | None = None,
    sources: list[dict[str, Any]] | None = None,
    commit: bool = True,
) -> Message:
    message = Message(
        user_id=user_id,
        role=role,
        content=content,
        document_id=document_id,
        sources=sources,
    )
    db.add(message)
    if commit:
        db.commit()
        db.refresh(message)
    else:
        db.flush()
    return message


def list_for_user(
    db: Session,
    *,
    user_id: uuid.UUID,
    document_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Message], int]:
    filters = [Message.user_id == user_id]
    if document_id is not None:
        filters.append(Message.document_id == document_id)

    total = db.scalar(select(func.count(Message.id)).where(*filters)) or 0
    messages = list(
        db.scalars(
            select(Message)
            .where(*filters)
            # created_at ties are possible within a single request, so break
            # them by insertion order to keep question/answer pairs adjacent.
            .order_by(Message.created_at.asc(), Message.role.asc())
            .limit(limit)
            .offset(offset)
        )
    )
    return messages, total
