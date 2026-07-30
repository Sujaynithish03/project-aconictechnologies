"""Gemini implementation of :class:`~app.services.llm.base.LLMProvider`.

Uses the current ``google-genai`` SDK. ``gemini-embedding-001`` is chosen over
the newer ``gemini-embedding-2`` because it supports asymmetric ``task_type``
and returns one embedding per input in a batched call — ``gemini-embedding-2``
aggregates multiple inputs into a single vector, which is wrong for chunk
indexing.
"""

import logging
from functools import lru_cache

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.exceptions import LLMUnavailableError

logger = logging.getLogger(__name__)

# Free-tier requests are rate limited, so batches stay modest.
EMBED_BATCH_SIZE = 32


class GeminiProvider:
    def __init__(
        self,
        api_key: str | None = None,
        chat_model: str | None = None,
        embedding_model: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        key = api_key or settings.gemini_api_key
        if not key:
            raise LLMUnavailableError(
                "GEMINI_API_KEY is not configured on the server."
            )
        self._client = genai.Client(api_key=key)
        self._chat_model = chat_model or settings.gemini_chat_model
        self._embedding_model = embedding_model or settings.gemini_embedding_model
        self._dimensions = dimensions or settings.embedding_dimensions

    @property
    def embedding_dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start : start + EMBED_BATCH_SIZE]
            vectors.extend(self._embed(batch, task_type="RETRIEVAL_DOCUMENT"))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], task_type="RETRIEVAL_QUERY")[0]

    def _embed(self, texts: list[str], *, task_type: str) -> list[list[float]]:
        try:
            response = self._client.models.embed_content(
                model=self._embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self._dimensions,
                ),
            )
        except Exception as error:
            logger.exception("Gemini embedding call failed")
            raise LLMUnavailableError(_friendly_error(error)) from error

        embeddings = response.embeddings or []
        if len(embeddings) != len(texts):
            raise LLMUnavailableError(
                "Embedding provider returned an unexpected number of vectors."
            )

        vectors: list[list[float]] = []
        for embedding in embeddings:
            values = embedding.values
            if not values:
                raise LLMUnavailableError("Embedding provider returned an empty vector.")
            # Truncated Matryoshka outputs need renormalising before cosine use;
            # the SDK only normalises the full 3072-dim output.
            vectors.append(_normalise(list(values)))
        return vectors

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=self._chat_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,  # Grounded answers, not creative ones.
                    max_output_tokens=2048,
                ),
            )
        except Exception as error:
            logger.exception("Gemini generation call failed")
            raise LLMUnavailableError(_friendly_error(error)) from error

        text = (response.text or "").strip()
        if not text:
            raise LLMUnavailableError(
                "The AI returned an empty response. Please rephrase your question."
            )
        return text


def _normalise(vector: list[float]) -> list[float]:
    magnitude = sum(value * value for value in vector) ** 0.5
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


def _friendly_error(error: Exception) -> str:
    message = str(error).lower()
    if "quota" in message or "429" in message or "resource_exhausted" in message:
        return (
            "The AI service rate limit was reached (Gemini free tier). "
            "Please wait a moment and try again."
        )
    if "api key" in message or "401" in message or "permission" in message:
        return "The AI service rejected the server's API key."
    return "The AI service is temporarily unavailable. Please try again."


@lru_cache
def get_llm_provider() -> GeminiProvider:
    """Cached provider — the SDK client is thread-safe and reusable."""
    return GeminiProvider()
