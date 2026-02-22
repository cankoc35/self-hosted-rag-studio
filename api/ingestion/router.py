"""
FastAPI router for ingestion endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile

from auth import dependencies as auth_dependencies

from . import embeddings
from . import repository
from . import service

router = APIRouter()


@router.get("/documents")
async def list_documents(
    current_user: dict = Depends(auth_dependencies.get_current_user),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """
    List current user's active documents (soft-deleted docs are excluded).
    """
    documents = await repository.list_documents(
        user_id=int(current_user["id"]),
        limit=limit,
        offset=offset,
    )
    return {
        "documents": documents,
        "limit": limit,
        "offset": offset,
        "count": len(documents),
    }


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    """
    Soft-delete a document owned by the current user.
    """
    row = await repository.soft_delete_document(document_id, user_id=int(current_user["id"]))
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {
        "ok": True,
        "document_id": int(row["id"]),
        "deleted_at": row["deleted_at"],
    }


@router.post("/documents")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    """
    Upload a document (.txt or .pdf), extract text, and (later) store it.

    Current behavior:
    - extracts text
    - returns basic metadata + extracted length/preview

    Next step:
    - insert into Postgres (raw SQL) and return a document id
    """
    result = await service.ingest_upload(file)
    chunks, chunking_meta = service.make_chunks(result.extracted_text)
    document_id, chunk_count = await repository.insert_document_and_chunks(
        user_id=int(current_user["id"]),
        filename=result.filename,
        content_type=result.content_type,
        size_bytes=result.size_bytes,
        extracted_text=result.extracted_text,
        chunks=chunks,
        metadata=chunking_meta,
    )

    # Start embedding after we return the HTTP response (Option B "light").
    background_tasks.add_task(
        embeddings.embed_document_background,
        document_id,
        user_id=int(current_user["id"]),
    )

    # Keep responses small; don't return full text.
    preview = result.extracted_text[:500]

    return {
        "document_id": document_id,
        "chunk_count": chunk_count,
        "embedding_started": True,
        "filename": result.filename,
        "content_type": result.content_type,
        "size_bytes": result.size_bytes,
        "file_ext": result.file_ext,
        "extracted_chars": len(result.extracted_text),
        "preview": preview,
    }


@router.post("/documents/{document_id}/embed")
async def embed_document(
    document_id: int,
    current_user: dict = Depends(auth_dependencies.get_current_user),
) -> dict:
    """
    Manual embedding trigger for an already-ingested document.

    This generates embeddings for chunks where `chunks.embedding IS NULL`.
    """
    stats = await embeddings.embed_document(document_id, user_id=int(current_user["id"]))
    return {
        "document_id": stats.document_id,
        "embedding_model": stats.model,
        "embedded": stats.embedded,
        "remaining": stats.remaining,
    }
