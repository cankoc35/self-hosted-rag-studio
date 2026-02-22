"""
Ingestion "service layer".

This file contains logic that is independent of FastAPI's routing layer:
- Validate uploads
- Read file bytes with a size limit
- Extract text from supported formats
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile

from . import chunking

ALLOWED_EXTENSIONS = {".txt", ".pdf"}

# Keep this conservative in dev; you can raise it later.
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB


@dataclass(frozen=True)
class IngestResult:
    filename: str
    content_type: str | None
    size_bytes: int
    file_ext: str
    extracted_text: str


def make_chunks(extracted_text: str) -> tuple[list[str], dict]:
    """
    Turn extracted document text into retrieval chunks.

    This uses `api/ingestion/chunking.py` and can be configured via env vars.
    """
    chunks, meta = chunking.chunk_text_with_metadata(extracted_text)
    if not chunks:
        raise HTTPException(status_code=422, detail="No chunks produced from extracted text.")
    return chunks, meta


def _file_ext(filename: str) -> str:
    return Path(filename).suffix.lower()


def validate_upload(file: UploadFile) -> str:
    """
    Return the normalized file extension if this upload is acceptable.

    We validate based on filename extension here because `content_type`
    is often missing or incorrect in practice.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")

    ext = _file_ext(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    return ext


async def read_upload_bytes(file: UploadFile, max_bytes: int) -> bytes:
    """
    Read the upload into memory, enforcing a maximum size.

    This is simplest to start with. If you later accept larger files,
    switch to streaming to disk/object storage instead of buffering in RAM.
    """
    chunk_size = 1024 * 1024  # 1 MiB
    buf = bytearray()

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max is {max_bytes} bytes.",
            )

    return bytes(buf)


async def ingest_upload(file: UploadFile) -> IngestResult:
    """
    High-level ingestion step for a single uploaded file.

    This is what the FastAPI router should call.
    """
    ext = validate_upload(file)
    max_bytes = max_upload_bytes_from_env()

    data = await read_upload_bytes(file, max_bytes=max_bytes)
    text = extract_text(ext, data)

    return IngestResult(
        filename=file.filename or "",
        content_type=file.content_type,
        size_bytes=len(data),
        file_ext=ext,
        extracted_text=text,
    )


def extract_text(ext: str, data: bytes) -> str:
    """
    Extract text from supported formats.

    `.txt` works out of the box.
    `.pdf` requires the optional `pypdf` dependency (no OCR).
    """
    if ext == ".txt":
        # Decode bytes to text. `replace` keeps the pipeline moving in early dev.
        return data.decode("utf-8", errors="replace")

    if ext == ".pdf":
        return _extract_pdf_text(data)

    # Defensive: validate_upload should prevent reaching here.
    raise HTTPException(status_code=400, detail=f"Unsupported extension: {ext}")


def _extract_pdf_text(data: bytes) -> str:
    """
    PDF text extraction using `pypdf` if available.

    Notes:
    - This extracts embedded text. Scanned PDFs need OCR (separate pipeline).
    - Extraction quality varies by PDF.
    """
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as e:
        # Make the failure mode explicit (instead of a generic 500).
        raise HTTPException(
            status_code=501,
            detail=(
                "PDF extraction is not enabled. Add `pypdf` to api/requirements.txt "
                "and rebuild: `docker compose build api`."
            ),
        ) from e

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail="Could not read PDF (file may be corrupted or unsupported).",
        ) from e

    # Some PDFs are encrypted. If it can't be decrypted with an empty password,
    # treat it as unsupported for now.
    if getattr(reader, "is_encrypted", False):
        try:
            decrypted = reader.decrypt("")  # returns 0/False-ish on failure
        except Exception:
            decrypted = 0
        if not decrypted:
            raise HTTPException(
                status_code=422,
                detail="Encrypted PDF is not supported.",
            )

    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            # Best-effort extraction: a single bad page shouldn't take down ingestion.
            parts.append("")

    text = "\n".join(parts).strip()
    if not text:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in PDF (scanned PDFs need OCR).",
        )

    return text

def max_upload_bytes_from_env() -> int:
    """
    Read MAX_UPLOAD_BYTES from env, falling back to a sane default.
    """
    raw = os.environ.get("MAX_UPLOAD_BYTES", "")
    if not raw:
        return DEFAULT_MAX_UPLOAD_BYTES

    try:
        value = int(raw)
    except ValueError:
        raise HTTPException(
            status_code=500,
            detail="Invalid MAX_UPLOAD_BYTES. It must be an integer.",
        )

    if value <= 0:
        raise HTTPException(
            status_code=500,
            detail="Invalid MAX_UPLOAD_BYTES. It must be > 0.",
        )

    return value
