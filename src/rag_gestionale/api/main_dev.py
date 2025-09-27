"""
API FastAPI in modalità sviluppo - funziona senza servizi esterni.
Usa mock per testing rapido senza Docker.
"""

import time
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from ..core.models import (
    SearchRequest,
    RAGResponse,
    QueryType,
    DocumentChunk,
    ChunkMetadata,
    SearchResult,
    ContentType,
    SourceFormat
)
from ..config.settings import get_settings
from .main import SearchQuery, IngestRequest, IngestResponse, HealthResponse


# Mock Components per sviluppo
class MockRAGComponents:
    def __init__(self):
        self.initialized = True
        self.mock_data = self._create_mock_data()

    async def initialize(self):
        """Mock inizializzazione"""
        pass

    async def cleanup(self):
        """Mock cleanup"""
        pass

    def _create_mock_data(self):
        """Crea dati mock per testing"""
        return {
            "chunks": [
                {
                    "id": "mock_001",
                    "title": "Configurazione Aliquota IVA",
                    "content": "Per configurare l'aliquota IVA predefinita:\n1. Accedere a Menu > Contabilità > Impostazioni\n2. Selezionare la scheda IVA\n3. Impostare il valore nel campo 'Aliquota predefinita'\n4. Salvare le modifiche",
                    "module": "Contabilità",
                    "content_type": "procedure",
                    "score": 0.95
                },
                {
                    "id": "mock_002",
                    "title": "Parametri Fatturazione",
                    "content": "I parametri di fatturazione includono:\n- Numerazione automatica\n- Template predefinito\n- Aliquote IVA\n- Modalità di pagamento",
                    "module": "Fatturazione",
                    "content_type": "parameter",
                    "score": 0.87
                },
                {
                    "id": "mock_003",
                    "title": "Errore IVA-102",
                    "content": "Errore IVA-102: Aliquota non valida\nCausa: L'aliquota specificata non è presente nell'anagrafica\nSoluzione: Verificare e aggiungere l'aliquota mancante",
                    "module": "Contabilità",
                    "content_type": "error",
                    "score": 0.82
                }
            ]
        }

    async def search(self, query: str, filters: Optional[Dict] = None, top_k: int = 5):
        """Mock ricerca"""
        # Simula delay
        await asyncio.sleep(0.1)

        # Filtra per query
        results = []
        query_lower = query.lower()

        for chunk_data in self.mock_data["chunks"]:
            if query_lower in chunk_data["title"].lower() or query_lower in chunk_data["content"].lower():
                # Crea mock chunk
                metadata = ChunkMetadata(
                    id=chunk_data["id"],
                    title=chunk_data["title"],
                    breadcrumbs=["Home", chunk_data["module"], chunk_data["title"]],
                    section_level=2,
                    section_path=f"{chunk_data['module'].lower()}/{chunk_data['id']}",
                    content_type=ContentType(chunk_data["content_type"]),
                    version="1.0",
                    module=chunk_data["module"],
                    source_url=f"https://docs.example.com/{chunk_data['id']}",
                    source_format=SourceFormat.HTML,
                    lang="it",
                    hash=f"hash_{chunk_data['id']}",
                    updated_at=datetime.now(),
                )

                chunk = DocumentChunk(
                    content=chunk_data["content"],
                    metadata=metadata
                )

                result = SearchResult(
                    chunk=chunk,
                    score=chunk_data["score"],
                    explanation=f"Mock match for: {query}"
                )

                results.append(result)

        return results[:top_k]

    async def ingest(self, urls: List[str]):
        """Mock ingestione"""
        await asyncio.sleep(0.5)  # Simula processing
        return len(urls) * 10  # Mock: 10 chunks per URL


# Singleton per componenti mock
import asyncio
mock_components = MockRAGComponents()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestione lifecycle applicazione"""
    # Startup
    await mock_components.initialize()
    print("🚀 Development mode - Using mock data (no external services required)")
    yield
    # Shutdown
    await mock_components.cleanup()


# Applicazione FastAPI
app = FastAPI(
    title="RAG Gestionale API - Development Mode",
    description="Sistema RAG in modalità sviluppo con dati mock",
    version="1.0.0-dev",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Pagina principale"""
    return """
    <html>
    <head>
        <title>RAG Gestionale - Dev Mode</title>
        <style>
            body { font-family: Arial; padding: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }
            .warning { background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0; }
            .endpoint { background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 5px; }
            code { background: #e9ecef; padding: 2px 5px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 RAG Gestionale - Development Mode</h1>

            <div class="warning">
                ⚠️ <strong>Modalità Sviluppo</strong><br>
                Questa è una versione mock che non richiede servizi esterni.<br>
                I dati sono simulati per testing rapido.
            </div>

            <h2>Endpoint disponibili:</h2>
            <div class="endpoint">
                <code>POST /search</code> - Ricerca con dati mock
            </div>
            <div class="endpoint">
                <code>POST /ingest</code> - Ingestione simulata
            </div>
            <div class="endpoint">
                <code>GET /health</code> - Health check
            </div>
            <div class="endpoint">
                <code>GET /docs</code> - Documentazione Swagger
            </div>

            <h3>Esempio di ricerca:</h3>
            <pre><code>
curl -X POST "http://localhost:8000/search" \\
  -H "Content-Type: application/json" \\
  -d '{"query": "aliquota IVA"}'
            </code></pre>
        </div>
    </body>
    </html>
    """


@app.post("/search")
async def search(request: SearchQuery):
    """Ricerca mock"""
    start_time = time.time()

    # Mock search
    results = await mock_components.search(
        query=request.query,
        filters=request.filters,
        top_k=request.top_k or 5
    )

    # Determina tipo query
    query_lower = request.query.lower()
    if "errore" in query_lower or "error" in query_lower:
        query_type = QueryType.ERROR
    elif "parametr" in query_lower or "impost" in query_lower:
        query_type = QueryType.PARAMETER
    elif "come" in query_lower or "procedura" in query_lower:
        query_type = QueryType.PROCEDURE
    else:
        query_type = QueryType.GENERAL

    # Genera risposta mock
    if results:
        answer = f"Trovati {len(results)} risultati per '{request.query}'.\n\n"
        answer += f"Risultato principale: {results[0].chunk.metadata.title}\n\n"
        answer += results[0].chunk.content
    else:
        answer = f"Nessun risultato trovato per '{request.query}'."

    processing_time_ms = int((time.time() - start_time) * 1000)

    return RAGResponse(
        query=request.query,
        query_type=query_type,
        answer=answer,
        sources=results,
        confidence=0.85 if results else 0.0,
        processing_time_ms=processing_time_ms,
    )


@app.post("/ingest")
async def ingest_documents(request: IngestRequest):
    """Ingestione mock"""
    start_time = time.time()

    urls = request.urls or []
    chunks_processed = await mock_components.ingest(urls)

    processing_time_ms = int((time.time() - start_time) * 1000)

    return IngestResponse(
        status="success",
        message=f"Mock ingestione completata per {len(urls)} URL",
        chunks_processed=chunks_processed,
        processing_time_ms=processing_time_ms,
    )


@app.get("/health")
async def health_check():
    """Health check"""
    return HealthResponse(
        status="healthy",
        version="1.0.0-dev",
        services={
            "vector_store": "mock",
            "lexical_search": "mock",
            "retriever": "mock",
            "generator": "mock",
        },
        stats={
            "mode": "development",
            "mock_chunks": len(mock_components.mock_data["chunks"]),
        }
    )


@app.get("/stats")
async def get_stats():
    """Statistiche mock"""
    return {
        "mode": "development",
        "mock_data": {
            "total_chunks": len(mock_components.mock_data["chunks"]),
            "modules": ["Contabilità", "Fatturazione", "Magazzino"],
            "content_types": ["procedure", "parameter", "error"],
        },
        "configuration": {
            "chunking": {
                "parent_max_tokens": 800,
                "child_proc_max_tokens": 350,
                "child_param_max_tokens": 200,
            },
            "retrieval": {
                "k_dense": 40,
                "k_lexical": 20,
                "k_final": 10,
            }
        }
    }


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("🚀 Starting RAG Gestionale in DEVELOPMENT MODE")
    print("📌 No external services required!")
    print("="*50 + "\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )