"""
API FastAPI principale per il sistema RAG gestionale.
Include endpoint per ricerca, ingestione e gestione documenti.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference

from ..config.settings import get_settings
from .dependencies import rag_components
from .routers import search, ingest, chunks, health, images


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestione lifecycle applicazione"""
    # Startup
    await rag_components.initialize()
    yield
    # Shutdown
    await rag_components.cleanup()


# Applicazione FastAPI
app = FastAPI(
    title="RAG Gestionale API",
    description="Sistema RAG specializzato per documentazione di gestionali",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/swagger",  # Swagger UI disponibile su /swagger
    redoc_url=None,  # Disabilita ReDoc per evitare duplicazioni
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione, specificare domini esatti
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router)
app.include_router(ingest.router)
app.include_router(chunks.router)
app.include_router(health.router)
app.include_router(images.router)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Pagina principale con documentazione"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>RAG Gestionale API</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .method { color: #fff; padding: 4px 8px; border-radius: 3px; font-weight: bold; }
            .get { background: #61affe; }
            .post { background: #49cc90; }
            code { background: #f0f0f0; padding: 2px 4px; border-radius: 3px; }
            .doc-link {
                display: inline-block;
                margin: 10px 10px 10px 0;
                padding: 10px 20px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
            }
            .doc-link:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>RAG Gestionale API</h1>
            <p>Sistema RAG specializzato per documentazione di gestionali in italiano.</p>

            <h2>📚 Documentazione Interattiva</h2>
            <div>
                <a href="/docs" class="doc-link">Scalar API Docs</a>
                <a href="/swagger" class="doc-link">Swagger UI</a>
            </div>

            <h2>📋 Endpoint Principali</h2>

            <div class="endpoint">
                <span class="method post">POST</span> <code>/search</code>
                <p>Ricerca semantica e lessicale nella documentazione (LLM sempre attivo)</p>
            </div>

            <div class="endpoint">
                <span class="method post">POST</span> <code>/ingest</code>
                <p>Ingestione di nuovi documenti da URL o directory</p>
            </div>

            <div class="endpoint">
                <span class="method get">GET</span> <code>/health</code>
                <p>Stato del sistema e statistiche</p>
            </div>

            <div class="endpoint">
                <span class="method get">GET</span> <code>/stats</code>
                <p>Statistiche dettagliate del sistema</p>
            </div>

            <div class="endpoint">
                <span class="method get">GET</span> <code>/chunks/{chunk_id}</code>
                <p>Recupera un chunk specifico</p>
            </div>

            <div class="endpoint">
                <span class="method delete">DELETE</span> <code>/chunks/{chunk_id}</code>
                <p>Elimina un chunk specifico</p>
            </div>

            <h2>🎯 Caratteristiche</h2>
            <ul>
                <li><strong>Ricerca ibrida</strong>: Vector + BM25 + Reranking</li>
                <li><strong>LLM sempre attivo</strong>: Generazione risposte intelligenti con OpenAI</li>
                <li><strong>Template tipizzati</strong>: Parametri, Procedure, Errori</li>
                <li><strong>Metadati ricchi</strong>: Moduli, versioni, UI paths</li>
                <li><strong>Anti-hallucination</strong>: Citazioni obbligatorie</li>
                <li><strong>Chunking intelligente</strong>: Parent/child con overlap</li>
            </ul>

            <h2>🚀 Esempio d'uso</h2>
            <pre><code>
curl -X POST "http://localhost:8000/search" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "Come impostare aliquota IVA predefinita?",
    "filters": {"module": "Contabilità"},
    "top_k": 5
  }'
            </code></pre>

            <h2>⚙️ Configurazione LLM</h2>
            <p>Il sistema utilizza sempre LLM per generare risposte. Configurare nel file .env:</p>
            <ul>
                <li><code>RAG_LLM__ENABLED=true</code></li>
                <li><code>RAG_LLM__API_KEY=your-api-key</code></li>
                <li><code>RAG_LLM__MODEL_NAME=gpt-4o-mini</code></li>
            </ul>
        </div>
    </body>
    </html>
    """
    return html_content


# Scalar documentation endpoint
@app.get("/docs", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "rag_gestionale.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=True,
    )
