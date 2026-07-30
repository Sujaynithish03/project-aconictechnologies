"""Retrieval-augmented question answering.

Flow: embed the question -> pgvector top-k over the caller's ready documents ->
build a grounded prompt from the retrieved passages -> generate -> persist the
exchange with its citations.
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import DocumentNotFoundError, NoDocumentsError
from app.crud import chunk as chunk_crud
from app.crud import document as document_crud
from app.crud import message as message_crud
from app.crud.chunk import RetrievedChunk
from app.models.document import DocumentStatus
from app.models.message import Message, MessageRole
from app.services.llm.base import LLMProvider
from app.services.llm.gemini import get_llm_provider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a precise document analyst for a knowledge base application.

Rules you must follow:
1. Answer using ONLY the numbered context passages provided. They are excerpts \
from documents the user uploaded.
2. If the passages do not contain the answer, say so plainly — for example: \
"The provided documents don't cover that." Never invent facts, figures, names, \
or dates.
3. Cite the passages you relied on inline using their numbers, like [1] or [2][3].
4. Prefer quoting exact figures, dates, and names from the passages over \
paraphrasing them.
5. Use short markdown bullet lists for multi-part answers (key points, dates, \
lists) and plain prose for single-fact answers.
6. Be concise. Do not restate the question or add meta-commentary about the \
passages."""

# A passage this dissimilar to the question is noise; dropping it keeps the
# prompt focused and makes "not in the documents" answers more reliable.
MIN_SIMILARITY = 0.30


@dataclass(frozen=True)
class AnswerResult:
    message: Message
    answer: str
    sources: list[RetrievedChunk]


def answer_question(
    db: Session,
    *,
    user_id: uuid.UUID,
    question: str,
    document_id: uuid.UUID | None = None,
    provider: LLMProvider | None = None,
) -> AnswerResult:
    question = question.strip()
    _assert_answerable(db, user_id=user_id, document_id=document_id)

    llm = provider or get_llm_provider()
    query_embedding = llm.embed_query(question)

    retrieved = chunk_crud.search(
        db,
        user_id=user_id,
        query_embedding=query_embedding,
        top_k=settings.retrieval_top_k,
        document_id=document_id,
    )
    relevant = [c for c in retrieved if c.similarity >= MIN_SIMILARITY]
    # If everything scored low, keep the single best hit so the model can still
    # judge relevance itself rather than being handed an empty context.
    sources = relevant or retrieved[:1]

    if sources:
        answer = llm.generate(SYSTEM_PROMPT, _build_prompt(question, sources))
    else:
        answer = (
            "I couldn't find anything relevant in your documents to answer that. "
            "Try rephrasing the question, or check that the right document is selected."
        )

    # Persist question and answer in one transaction so history can never
    # contain an orphaned half of an exchange.
    message_crud.create(
        db,
        user_id=user_id,
        role=MessageRole.USER,
        content=question,
        document_id=document_id,
        commit=False,
    )
    assistant_message = message_crud.create(
        db,
        user_id=user_id,
        role=MessageRole.ASSISTANT,
        content=answer,
        document_id=document_id,
        sources=[_serialise(source) for source in sources],
        commit=False,
    )
    db.commit()
    db.refresh(assistant_message)

    return AnswerResult(message=assistant_message, answer=answer, sources=sources)


def _assert_answerable(
    db: Session, *, user_id: uuid.UUID, document_id: uuid.UUID | None
) -> None:
    """Fail fast with an actionable message before spending an LLM call."""
    if document_id is not None:
        document = document_crud.get_for_user(
            db, document_id=document_id, user_id=user_id
        )
        if document is None:
            raise DocumentNotFoundError()
        if document.status is not DocumentStatus.READY:
            raise NoDocumentsError(
                f"'{document.filename}' is not ready yet (status: "
                f"{document.status.value}). Wait for processing to finish."
            )
        return

    if document_crud.count_ready_for_user(db, user_id=user_id) == 0:
        raise NoDocumentsError()


def _build_prompt(question: str, sources: list[RetrievedChunk]) -> str:
    blocks = [
        f"[{index}] (from \"{source.document_name}\")\n{source.content}"
        for index, source in enumerate(sources, start=1)
    ]
    context = "\n\n---\n\n".join(blocks)
    return (
        f"Context passages:\n\n{context}\n\n"
        f"---\n\nQuestion: {question}\n\n"
        "Answer using only the passages above, citing them by number."
    )


def _serialise(source: RetrievedChunk) -> dict[str, object]:
    return {
        "document_id": str(source.document_id),
        "document_name": source.document_name,
        "chunk_index": source.chunk_index,
        # Store a snippet rather than the full chunk to keep history rows small.
        "snippet": source.content[:600],
        "similarity": source.similarity,
    }
