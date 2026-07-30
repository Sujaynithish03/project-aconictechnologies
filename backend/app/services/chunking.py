"""Split extracted text into overlapping chunks for embedding.

Chunks respect natural boundaries (paragraph, then sentence, then word) so a
retrieved passage reads as coherent prose rather than a mid-word fragment. The
overlap keeps facts that straddle a boundary retrievable from either side.
"""

import re

from app.core.config import settings

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Return non-empty chunks of roughly ``chunk_size`` characters."""
    size = chunk_size if chunk_size is not None else settings.chunk_size
    step_back = overlap if overlap is not None else settings.chunk_overlap

    if size <= 0:
        raise ValueError("chunk_size must be positive")
    if not 0 <= step_back < size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    text = text.strip()
    if not text:
        return []

    units = _split_into_units(text, size)

    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= size:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = _tail(current, step_back)
            candidate = f"{current}\n\n{unit}" if current else unit
            if len(candidate) <= size:
                current = candidate
                continue

        # The unit alone still overflows even after trimming: emit it directly.
        current = unit

    if current.strip():
        chunks.append(current)

    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _split_into_units(text: str, size: int) -> list[str]:
    """Break text into pieces no larger than ``size``, preferring clean seams."""
    units: list[str] = []
    for paragraph in _PARAGRAPH_SPLIT.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= size:
            units.append(paragraph)
            continue

        for sentence in _SENTENCE_SPLIT.split(paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= size:
                units.append(sentence)
            else:
                units.extend(_split_on_words(sentence, size))
    return units


def _split_on_words(text: str, size: int) -> list[str]:
    """Last-resort splitter for text with no sentence punctuation."""
    pieces: list[str] = []
    current: list[str] = []
    length = 0
    for word in text.split():
        # A single word longer than the limit gets hard-sliced.
        if len(word) > size:
            if current:
                pieces.append(" ".join(current))
                current, length = [], 0
            pieces.extend(word[i : i + size] for i in range(0, len(word), size))
            continue
        if length + len(word) + 1 > size and current:
            pieces.append(" ".join(current))
            current, length = [], 0
        current.append(word)
        length += len(word) + 1
    if current:
        pieces.append(" ".join(current))
    return pieces


def _tail(text: str, overlap: int) -> str:
    """Return the trailing ``overlap`` characters, snapped to a word boundary."""
    if overlap <= 0 or len(text) <= overlap:
        return "" if overlap <= 0 else text
    tail = text[-overlap:]
    space = tail.find(" ")
    return tail[space + 1 :].strip() if space != -1 else tail.strip()
