"""Document embedding — the second phase of ingestion.

Phase 1 happens inside ``POST /upload``: validate the file, extract its text, and
store the document as ``pending``. That is pure CPU work with no network call, so
it always returns quickly (see ``app.services.extraction``).

Phase 2 lives here and runs from ``POST /documents/{id}/process``: chunk the
stored text, embed every chunk, and mark the document ``ready``. This is the slow
half — it calls the LLM once per batch.

Splitting them means the upload request never blocks on embedding, the document
status genuinely moves ``pending -> processing -> ready``, and a failed embed can
be retried without re-uploading the file. It also behaves identically on a
long-running server and on a serverless platform that freezes the process
between requests.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import AppError, DocumentNotFoundError
from app.crud import chunk as chunk_crud
from app.crud import document as document_crud
from app.models.document import Document, DocumentStatus
from app.services.chunking import chunk_text
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


def embed_document(
    db: Session,
    *,
    document_id: uuid.UUID,
    provider: LLMProvider,
) -> Document:
    """Chunk and embed a document's stored text, recording success or failure.

    Never raises for content problems: the outcome is written to the document's
    ``status`` and ``error_message`` so the dashboard can display it.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError()

    try:
        if not document.raw_text:
            raise AppError(
                "No extracted text is stored for this document. Re-upload it."
            )

        document.status = DocumentStatus.PROCESSING
        db.commit()

        chunks = chunk_text(document.raw_text)
        if not chunks:
            raise AppError("Document produced no usable text chunks.")

        embeddings = provider.embed_documents(chunks)

        # Replace rather than append, so re-processing never duplicates chunks.
        chunk_crud.delete_for_document(db, document_id=document_id)
        chunk_crud.bulk_create(
            db, document_id=document_id, contents=chunks, embeddings=embeddings
        )

        document = document_crud.set_status(
            db,
            document=document,
            status=DocumentStatus.READY,
            chunk_count=len(chunks),
        )
        logger.info(
            "Embedded document %s: %d chars, %d chunks",
            document_id,
            document.char_count,
            len(chunks),
        )
        return document

    except AppError as error:
        return _mark_failed(db, document_id, error.detail)
    except Exception as error:  # noqa: BLE001 - must not escape a background task
        logger.exception("Unexpected embedding failure for %s", document_id)
        return _mark_failed(db, document_id, f"Processing failed: {error}")


def embed_document_in_background(
    document_id: uuid.UUID, provider: LLMProvider
) -> None:
    """Entry point for FastAPI BackgroundTasks, which own their own session.

    The request-scoped session is already closed by the time this runs.
    """
    from app.db.session import SessionLocal  # noqa: PLC0415

    db = SessionLocal()
    try:
        embed_document(db, document_id=document_id, provider=provider)
    except Exception:
        logger.exception("Background embedding failed for %s", document_id)
    finally:
        db.close()


def _mark_failed(db: Session, document_id: uuid.UUID, message: str) -> Document:
    db.rollback()
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError()
    return document_crud.set_status(
        db,
        document=document,
        status=DocumentStatus.FAILED,
        error_message=message[:1000],
    )
