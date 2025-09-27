"""
Dependencies condivise per l'API FastAPI.
"""

from typing import Optional

from fastapi import HTTPException

from ..retrieval.hybrid_retriever import HybridRetriever
from ..generation.generator import ResponseGenerator
from ..ingest.coordinator import IngestionCoordinator


class RAGComponents:
    """Singleton per componenti del sistema RAG"""

    def __init__(self):
        self.retriever: Optional[HybridRetriever] = None
        self.generator: Optional[ResponseGenerator] = None
        self.ingestion_coordinator: Optional[IngestionCoordinator] = None
        self.initialized = False

    async def initialize(self):
        """Inizializza tutti i componenti"""
        if self.initialized:
            return

        self.retriever = HybridRetriever()
        await self.retriever.initialize()

        self.generator = ResponseGenerator()
        await self.generator.initialize()

        self.ingestion_coordinator = IngestionCoordinator()

        self.initialized = True

    async def cleanup(self):
        """Cleanup componenti"""
        if self.retriever:
            await self.retriever.close()


# Istanza globale
rag_components = RAGComponents()


def get_components() -> RAGComponents:
    """Dependency per componenti RAG"""
    if not rag_components.initialized:
        raise HTTPException(status_code=503, detail="Servizio non inizializzato")
    return rag_components
