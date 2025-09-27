"""
Router per gli endpoint di ingestione documenti.
"""

import time
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from ..dependencies import get_components, RAGComponents


class IngestRequest(BaseModel):
    """Richiesta di ingestione"""

    urls: Optional[List[str]] = Field(None, description="URL da processare")
    directory: Optional[str] = Field(None, description="Directory da processare")


class IngestResponse(BaseModel):
    """Risposta ingestione"""

    status: str
    message: str
    chunks_processed: int
    processing_time_ms: int


router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
async def ingest_documents(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    components: RAGComponents = Depends(get_components),
) -> IngestResponse:
    """
    Ingestione di nuovi documenti nel sistema.

    Supporta:
    - URL singoli o multipli
    - Directory locali (PDF/HTML)
    - Processing in background per grandi volumi
    """
    start_time = time.time()

    if not request.urls and not request.directory:
        raise HTTPException(
            status_code=400, detail="Specificare almeno un URL o una directory"
        )

    try:
        # Ingestione sincrona per small jobs
        chunks_processed = 0

        if request.urls:
            chunks = await components.ingestion_coordinator.ingest_from_urls(
                request.urls
            )
            if chunks:
                await components.retriever.add_chunks(chunks)
                chunks_processed += len(chunks)

        if request.directory:
            chunks = await components.ingestion_coordinator.ingest_from_directory(
                request.directory
            )
            if chunks:
                await components.retriever.add_chunks(chunks)
                chunks_processed += len(chunks)

        processing_time_ms = int((time.time() - start_time) * 1000)

        return IngestResponse(
            status="success",
            message=f"Ingestione completata con successo",
            chunks_processed=chunks_processed,
            processing_time_ms=processing_time_ms,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Errore durante l'ingestione: {str(e)}"
        )
