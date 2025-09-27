"""
Router per gli endpoint di health check e statistiche.
"""

from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...config.settings import get_settings
from ..dependencies import get_components, RAGComponents


class HealthResponse(BaseModel):
    """Risposta health check"""

    status: str
    version: str
    services: Dict[str, str]
    stats: Dict[str, Any]


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    components: RAGComponents = Depends(get_components),
) -> HealthResponse:
    """
    Health check del sistema con statistiche
    """
    try:
        # Statistiche del retriever
        stats = await components.retriever.get_stats()

        # Statistiche di ingestione
        ingest_stats = await components.ingestion_coordinator.get_processing_stats()

        return HealthResponse(
            status="healthy",
            version="1.0.0",
            services={
                "vector_store": "healthy",
                "lexical_search": "healthy",
                "retriever": "healthy",
                "generator": "healthy",
                "llm": "enabled"
                if components.generator.settings.llm.enabled
                else "disabled",
            },
            stats={
                "retrieval": stats,
                "ingestion": ingest_stats,
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Servizio non disponibile: {str(e)}"
        )


@router.get("/stats")
async def get_detailed_stats(
    components: RAGComponents = Depends(get_components),
) -> Dict[str, Any]:
    """Statistiche dettagliate del sistema"""
    try:
        retrieval_stats = await components.retriever.get_stats()
        ingestion_stats = await components.ingestion_coordinator.get_processing_stats()

        settings = get_settings()

        return {
            "system": {
                "version": "1.0.0",
                "status": "healthy",
                "uptime": "N/A",  # Da implementare se necessario
            },
            "retrieval": retrieval_stats,
            "ingestion": ingestion_stats,
            "configuration": {
                "chunking": {
                    "parent_max_tokens": settings.chunking.parent_max_tokens,
                    "child_proc_max_tokens": settings.chunking.child_proc_max_tokens,
                    "child_param_max_tokens": settings.chunking.child_param_max_tokens,
                },
                "retrieval": {
                    "k_dense": settings.retrieval.k_dense,
                    "k_lexical": settings.retrieval.k_lexical,
                    "k_final": settings.retrieval.k_final,
                },
                "embedding": {
                    "model": settings.embedding.model_name,
                    "batch_size": settings.embedding.batch_size,
                },
                "llm": {
                    "enabled": settings.llm.enabled,
                    "model": settings.llm.model_name if settings.llm.enabled else None,
                    "temperature": settings.llm.temperature,
                },
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Errore recupero statistiche: {str(e)}"
        )
