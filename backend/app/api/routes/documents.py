"""Document routes: /upload, /documents."""

import uuid

from fastapi import APIRouter, BackgroundTasks, File, Query, Request, UploadFile, status

from app.api.deps import CurrentUser, DbSession, LLMFactory
from app.core.config import settings
from app.core.exceptions import (
    DocumentNotFoundError,
    EmptyFileError,
    FileTooLargeError,
)
from app.crud import document as document_crud
from app.models.document import DocumentStatus
from app.schemas.document import DeleteResponse, DocumentListResponse, DocumentRead
from app.services.extraction import extract_text, resolve_extension, validate_upload
from app.services.ingestion import embed_document, embed_document_in_background

router = APIRouter(tags=["documents"])

# Multipart framing adds a few hundred bytes of boundaries and headers on top of
# the file itself; allow a small margin before rejecting on Content-Length.
MULTIPART_OVERHEAD_BYTES = 4096


def _reject_oversized_request(request: Request) -> None:
    """Raise 413 from the Content-Length header, before the body is read."""
    raw_length = request.headers.get("content-length")
    if raw_length is None:
        return  # Chunked upload; the post-read size check still applies.
    try:
        declared = int(raw_length)
    except ValueError:
        return
    if declared > settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES:
        raise FileTooLargeError(
            f"File is {declared / 1_048_576:.1f} MB; the limit is "
            f"{settings.max_upload_mb} MB."
        )


@router.post(
    "/upload",
    response_model=DocumentRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a PDF, DOCX, or TXT document for processing",
)
async def upload_document(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(..., description="PDF, DOCX, or TXT, max 10 MB"),
) -> DocumentRead:
    """Validate the file and extract its text, then stage it for embedding.

    Returns ``202`` with ``status="pending"``. Embedding is a separate call —
    ``POST /documents/{id}/process`` — so this request never blocks on the LLM.
    """
    if not file.filename:
        raise EmptyFileError("No filename was provided.")

    # Reject on the declared size and extension before buffering the body, so an
    # oversized upload never has to be held in memory to be turned away.
    _reject_oversized_request(request)
    resolve_extension(file.filename)

    data = await file.read()
    # Validate fully so a bad file reports 415/413 rather than failing later.
    extension = validate_upload(file.filename, file.content_type, data)

    # Extraction is pure CPU work with no network call, so it stays inline. It
    # runs *before* the row is created, so an unreadable file raises 400 without
    # leaving an unusable document in the user's library.
    text = extract_text(data, extension)

    # Only the text is persisted; the raw bytes are discarded.
    document = document_crud.create(
        db,
        user_id=current_user.id,
        filename=file.filename[:255],
        file_type=extension,
        size_bytes=len(data),
        raw_text=text,
    )

    return DocumentRead.model_validate(document)


@router.post(
    "/documents/{document_id}/process",
    response_model=DocumentRead,
    summary="Chunk and embed an uploaded document",
)
def process_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
    build_llm: LLMFactory,
) -> DocumentRead:
    """Run the embedding phase for a document that has been uploaded.

    Safe to call again on a document that failed, which retries it without a
    re-upload. On a long-running server the work is handed to a background task
    and this returns ``processing``; on a serverless host — where the process is
    frozen once the response is sent — it runs inline and returns the finished
    state.
    """
    document = document_crud.get_for_user(
        db, document_id=document_id, user_id=current_user.id
    )
    if document is None:
        raise DocumentNotFoundError()

    if document.status is DocumentStatus.READY:
        return DocumentRead.model_validate(document)  # Already indexed; no-op.

    # Resolve the provider first so a missing API key is a clean 503.
    llm = build_llm()

    if settings.defer_embedding:
        document = document_crud.set_status(
            db, document=document, status=DocumentStatus.PROCESSING
        )
        background_tasks.add_task(embed_document_in_background, document_id, llm)
        return DocumentRead.model_validate(document)

    document = embed_document(db, document_id=document_id, provider=llm)
    return DocumentRead.model_validate(document)


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List the current user's documents, newest first",
)
def list_documents(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DocumentListResponse:
    documents, total = document_crud.list_for_user(
        db, user_id=current_user.id, limit=limit, offset=offset
    )
    return DocumentListResponse(
        documents=[DocumentRead.model_validate(d) for d in documents], total=total
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentRead,
    summary="Fetch one document — used to poll processing status",
)
def get_document(
    document_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> DocumentRead:
    document = document_crud.get_for_user(
        db, document_id=document_id, user_id=current_user.id
    )
    if document is None:
        raise DocumentNotFoundError()
    return DocumentRead.model_validate(document)


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteResponse,
    summary="Delete a document and its embedded chunks",
)
def delete_document(
    document_id: uuid.UUID, current_user: CurrentUser, db: DbSession
) -> DeleteResponse:
    document = document_crud.get_for_user(
        db, document_id=document_id, user_id=current_user.id
    )
    if document is None:
        raise DocumentNotFoundError()

    filename = document.filename
    document_crud.delete(db, document=document)
    return DeleteResponse(detail=f"Deleted '{filename}'.")


@router.get(
    "/documents-config",
    summary="Upload constraints, so the client can validate before sending",
)
def document_config() -> dict[str, object]:
    return {
        "max_upload_mb": settings.max_upload_mb,
        "allowed_extensions": ["pdf", "docx", "txt"],
    }
