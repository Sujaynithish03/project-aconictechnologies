"""Provider-agnostic LLM interface.

The RAG service depends only on this Protocol, so swapping Gemini for another
provider means adding one module — and tests can substitute a stub without
touching the network.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    @property
    def embedding_dimensions(self) -> int:
        """Length of the vectors this provider returns."""
        ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed passages for indexing. Returns one vector per input, in order."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query. Asymmetric task type improves retrieval."""
        ...

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return a completion for the given prompts."""
        ...
