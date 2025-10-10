"""
Router per gli endpoint di ricerca.
"""

import time
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from ...core.models import RAGResponse, QueryType
from ..dependencies import get_components, RAGComponents


class SearchQuery(BaseModel):
    """Richiesta di ricerca"""

    query: str = Field(..., description="Query di ricerca", min_length=1)
    filters: Optional[Dict[str, Any]] = Field(None, description="Filtri opzionali")
    top_k: Optional[int] = Field(10, description="Numero di risultati", ge=1, le=50)
    include_sources: bool = Field(True, description="Includere fonti nella risposta")


router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=RAGResponse)
async def search(
    request: SearchQuery, components: RAGComponents = Depends(get_components)
) -> RAGResponse:
    """
    Ricerca nella documentazione con sistema RAG ibrido.

    Il sistema utilizza sempre LLM per generare risposte di qualità,
    con configurazione presa dal file .env.

    Supporta:
    - Ricerca semantica (embeddings)
    - Ricerca lessicale (BM25)
    - Reranking con cross-encoder
    - Generazione risposte con LLM (sempre attivo)
    """
    start_time = time.time()

    try:
        logger.info(f"Ricerca avviata per query: '{request.query}'")

        # Ricerca ibrida
        logger.debug("Inizio ricerca ibrida...")
        search_results = await components.retriever.search(
            query=request.query,
            top_k=request.top_k,
            filters=request.filters,
        )
        logger.info(f"Ricerca completata: {len(search_results)} risultati trovati")

        if not search_results:
            # Nessun risultato trovato
            logger.warning("Nessun risultato trovato per la query")
            return RAGResponse(
                query=request.query,
                query_type=QueryType.GENERAL,
                answer="Nessuna informazione trovata per la query specificata.",
                sources=[],
                confidence=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        # Classifica query per template appropriato
        logger.debug("Classificazione query...")
        query_type = components.retriever.query_classifier.classify_query(request.query)
        logger.info(f"Query classificata come: {query_type}")

        # Genera risposta con LLM (se configurato) o template
        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info("Inizio generazione risposta...")
        response = await components.generator.generate_response(
            query=request.query,
            query_type=query_type,
            search_results=search_results,
            processing_time_ms=processing_time_ms,
        )
        logger.info("Risposta generata con successo")

        # Filtra fonti se richiesto
        if not request.include_sources:
            response.sources = []

        logger.info(f"Ricerca completata in {processing_time_ms}ms")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore durante la ricerca: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Errore durante la ricerca: {str(e)}"
        )
