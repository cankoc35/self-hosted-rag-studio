"""
Chunking utilities.

Goal: turn extracted document text into reasonably-sized chunks for retrieval.

Default behavior:
- target chunk size: 1000 chars
- overlap: 100 chars
- if the final chunk is smaller than min_chunk, merge it into the previous chunk
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any


DEFAULT_CHUNK_SIZE_CHARS = 1000
DEFAULT_CHUNK_OVERLAP_CHARS = 100
DEFAULT_MIN_CHUNK_CHARS = 350


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value


def chunk_settings() -> tuple[int, int, int, str, bool]:
    """
    Returns (chunk_size, overlap, min_chunk, language, use_spacy).

    - CHUNK_SIZE_CHARS: target chunk size in characters
    - CHUNK_OVERLAP_CHARS: overlap between chunks in characters
    - CHUNK_MIN_CHARS: final chunk smaller than this gets merged into the previous
    - CHUNK_LANGUAGE: spaCy blank pipeline language (default: xx)
    - CHUNK_USE_SPACY: "1" to prefer spaCy sentence segmentation when available
    """
    chunk_size = _env_int("CHUNK_SIZE_CHARS", DEFAULT_CHUNK_SIZE_CHARS)
    overlap = _env_int("CHUNK_OVERLAP_CHARS", DEFAULT_CHUNK_OVERLAP_CHARS)
    min_chunk = _env_int("CHUNK_MIN_CHARS", DEFAULT_MIN_CHUNK_CHARS)
    language = os.environ.get("CHUNK_LANGUAGE", "xx").strip() or "xx"
    use_spacy = os.environ.get("CHUNK_USE_SPACY", "1").strip() not in {"0", "false", "False"}
    return chunk_size, overlap, min_chunk, language, use_spacy


def chunk_text(text: str) -> list[str]:
    """
    Chunk text using the configured strategy.
    """
    chunks, _meta = chunk_text_with_metadata(text)
    return chunks


def chunk_text_with_metadata(text: str) -> tuple[list[str], dict[str, Any]]:
    chunk_size, overlap, min_chunk, language, use_spacy = chunk_settings()
    chunks, strategy, extra = _chunk_text_internal(
        text,
        chunk_size_chars=chunk_size,
        overlap_chars=overlap,
        min_chunk_chars=min_chunk,
        language=language,
        use_spacy=use_spacy,
    )
    meta: dict[str, Any] = {
        "chunking": {
            "strategy": strategy,
            "chunk_size_chars": chunk_size,
            "overlap_chars": overlap,
            "min_chunk_chars": min_chunk,
            "language": language,
            "use_spacy_requested": use_spacy,
            **extra,
        }
    }
    return chunks, meta


def chunk_text_configured(
    text: str,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
    min_chunk_chars: int,
    language: str = "xx",
    use_spacy: bool = True,
) -> list[str]:
    chunks, _strategy, _extra = _chunk_text_internal(
        text,
        chunk_size_chars=chunk_size_chars,
        overlap_chars=overlap_chars,
        min_chunk_chars=min_chunk_chars,
        language=language,
        use_spacy=use_spacy,
    )
    return chunks


def _chunk_text_internal(
    text: str,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
    min_chunk_chars: int,
    language: str,
    use_spacy: bool,
) -> tuple[list[str], str, dict[str, Any]]:
    """
    Returns (chunks, strategy, extra_metadata).
    """
    text = (text or "").strip()
    if not text:
        return [], "empty", {}

    if chunk_size_chars <= 0:
        raise ValueError("chunk_size_chars must be > 0")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be >= 0")
    if overlap_chars >= chunk_size_chars:
        # Overlap can't be >= chunk size, otherwise the window doesn't progress.
        overlap_chars = max(0, chunk_size_chars // 10)

    extra: dict[str, Any] = {}

    # Prefer sentence-aware chunking when available.
    if use_spacy and _spacy_available():
        chunks, had_long_sentence_fallback = _chunk_sentence_aware(
            text,
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
            language=language,
        )
        strategy = "spacy_sentencizer"
        extra["spacy_available"] = True
        extra["had_long_sentence_fallback"] = had_long_sentence_fallback
    else:
        chunks = _chunk_simple(
            text,
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
        )
        strategy = "simple_chars"
        extra["spacy_available"] = _spacy_available()

    chunks = [c.strip() for c in chunks if c.strip()]

    # Merge a small leftover final chunk.
    if len(chunks) >= 2 and len(chunks[-1]) < min_chunk_chars:
        chunks[-2] = (chunks[-2].rstrip() + "\n\n" + chunks[-1].lstrip()).strip()
        chunks.pop()
        extra["merged_final_small_chunk"] = True
    else:
        extra["merged_final_small_chunk"] = False

    return chunks, strategy, extra


def _chunk_simple(text: str, *, chunk_size_chars: int, overlap_chars: int) -> list[str]:
    """
    Pure character windowing: [0:chunk], then advance by (chunk - overlap).
    """
    step = max(1, chunk_size_chars - overlap_chars)
    out: list[str] = []
    i = 0
    while i < len(text):
        out.append(text[i : i + chunk_size_chars])
        i += step
    return out


def _spacy_available() -> bool:
    try:
        import spacy  # noqa: F401
    except Exception:
        return False
    return True


@lru_cache(maxsize=8)
def _get_spacy_nlp(language: str):
    """
    Create a small spaCy pipeline for sentence segmentation.
    """
    import spacy

    nlp = spacy.blank(language)
    if "sentencizer" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer")
    return nlp


def _chunk_sentence_aware(
    text: str,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
    language: str,
) -> tuple[list[str], bool]:
    """
    Pack sentences into chunks until we hit ~chunk_size_chars.

    Overlap is applied as the last N characters of the previous chunk.
    """
    nlp = _get_spacy_nlp(language)
    doc = nlp(text)

    chunks: list[str] = []
    current = ""
    had_long_sentence_fallback = False

    def flush() -> str:
        nonlocal current
        chunk = current.strip()
        current = ""
        return chunk

    for sent in doc.sents:
        s = sent.text.strip()
        if not s:
            continue

        # If a single sentence is longer than the chunk size, fall back to simple splitting.
        if len(s) > chunk_size_chars:
            had_long_sentence_fallback = True
            if current.strip():
                chunks.append(flush())
            chunks.extend(_chunk_simple(s, chunk_size_chars=chunk_size_chars, overlap_chars=overlap_chars))
            continue

        if not current:
            current = s
            continue

        if len(current) + 1 + len(s) > chunk_size_chars:
            chunk = flush()
            if chunk:
                chunks.append(chunk)
                if overlap_chars:
                    current = chunk[-overlap_chars:].strip()
            # Start (or continue) the new chunk with this sentence.
            current = (current + " " + s).strip() if current else s
        else:
            current = (current + " " + s).strip()

    last = flush()
    if last:
        chunks.append(last)

    return chunks, had_long_sentence_fallback
