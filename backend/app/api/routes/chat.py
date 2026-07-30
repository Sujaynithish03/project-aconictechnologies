"""Chat routes: /ask, /history."""

import uuid

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession, LLMFactory
from app.crud import message as message_crud
from app.schemas.chat import AskRequest, AskResponse, HistoryResponse, MessageRead, SourceChunk
from app.services import rag

router = APIRouter(tags=["chat"])


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a question answered from the user's uploaded documents",
)
def ask(
    payload: AskRequest, current_user: CurrentUser, db: DbSession, build_llm: LLMFactory
) -> AskResponse:
    """Retrieve relevant passages and generate a grounded answer.

    Omit ``document_id`` to search across every processed document the user owns.
    """
    result = rag.answer_question(
        db,
        user_id=current_user.id,
        question=payload.question,
        document_id=payload.document_id,
        provider=build_llm(),
    )
    return AskResponse(
        message_id=result.message.id,
        question=payload.question.strip(),
        answer=result.answer,
        sources=[
            SourceChunk(
                document_id=source.document_id,
                document_name=source.document_name,
                chunk_index=source.chunk_index,
                snippet=source.content[:600],
                similarity=source.similarity,
            )
            for source in result.sources
        ],
        created_at=result.message.created_at,
    )


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="Chat history in chronological order",
)
def history(
    current_user: CurrentUser,
    db: DbSession,
    document_id: uuid.UUID | None = Query(
        default=None, description="Filter to one document's conversation"
    ),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> HistoryResponse:
    messages, total = message_crud.list_for_user(
        db,
        user_id=current_user.id,
        document_id=document_id,
        limit=limit,
        offset=offset,
    )
    return HistoryResponse(
        messages=[MessageRead.model_validate(m) for m in messages], total=total
    )
