# Analisi Miglioramenti - RAG Gestionale

## 📊 Stato Attuale del Progetto

Il sistema RAG è **ben architettato** con:
- Hybrid retrieval (semantic + lexical)
- Supporto OCR e immagini
- Query classification intelligente
- Anti-hallucination controls
- Configurazione flessibile

### Architettura Attuale

**Componenti Principali:**
- **Backend**: FastAPI con async/await
- **Frontend**: Streamlit web UI
- **Vector Store**: Qdrant (HNSW index)
- **Lexical Search**: OpenSearch (BM25)
- **LLM**: OpenAI GPT-4o-mini
- **Embeddings**: BAAI/bge-m3
- **Reranker**: BAAI/bge-reranker-large
- **OCR**: Tesseract (italiano + inglese)

**Statistiche Codebase:**
- ~33 moduli Python sorgente
- ~3,500+ linee di codice
- 7 moduli principali (api, core, config, ingest, retrieval, generation)
- 6+ endpoint API core
- File più grandi: coordinator.py (538 righe), generator.py (478 righe)

---

## 🎯 Miglioramenti Proposti (Prioritizzati)

---

## PRIORITÀ ALTA 🔴

### 1. Test Suite Completa

**Problema**: Zero test automatici presenti nel progetto

**Impatto**:
- Rischio elevato di regressioni
- Difficoltà nel refactoring sicuro
- Mancanza di confidenza nelle modifiche

**Soluzione**:
```
tests/
├── unit/
│   ├── test_chunker.py
│   ├── test_embeddings.py
│   ├── test_retriever.py
│   ├── test_generator.py
│   └── test_parsers.py
├── integration/
│   ├── test_api_search.py
│   ├── test_api_ingest.py
│   └── test_vector_store.py
└── e2e/
    ├── test_full_pipeline.py
    └── test_ui_flows.py
```

**Implementazione**:
- Unit tests per tutti i moduli core
- Integration tests per API endpoints
- E2E tests per flussi completi di ingestion/search
- Mock per servizi esterni (OpenAI, Qdrant, OpenSearch)
- Fixtures per dati di test
- Coverage target: 80%+

**Tool**:
- pytest + pytest-asyncio (già nelle dipendenze)
- pytest-cov per coverage report
- pytest-mock per mocking
- httpx per test API

**Stima**: 3-5 giorni

---

### 2. Sicurezza & Autenticazione

**Problemi Attuali**:
- ❌ CORS configurato con `allow_origins=['*']`
- ❌ Nessuna autenticazione sugli endpoint
- ❌ API key OpenAI in chiaro nel .env
- ❌ Nessun rate limiting
- ❌ Nessun audit logging

**Rischi**:
- Accesso non autorizzato al sistema
- Abuso delle risorse (costi OpenAI)
- Esposizione dati sensibili
- Attacchi DoS

**Soluzioni**:

#### 2.1 API Key Authentication
```python
# Implementare middleware per validazione API key
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def validate_api_key(api_key: str = Security(api_key_header)):
    if api_key not in settings.valid_api_keys:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

#### 2.2 CORS Specifico
```python
# Configurare domini whitelisted
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # ["https://app.example.com"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

#### 2.3 Rate Limiting
```python
# Usare slowapi o fastapi-limiter
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/search")
@limiter.limit("10/minute")
async def search(request: Request, ...):
    ...
```

#### 2.4 Secrets Management
- Migrare da .env a Azure Key Vault / HashiCorp Vault
- Rotazione automatica API keys
- Encryption at rest per dati sensibili

#### 2.5 Audit Logging
```python
# Loggare tutte le richieste con metadata
@app.middleware("http")
async def audit_log_middleware(request: Request, call_next):
    logger.info(
        "api_request",
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host,
        user_agent=request.headers.get("user-agent"),
        api_key_hash=hash(request.headers.get("x-api-key", "")),
    )
    response = await call_next(request)
    return response
```

**Stima**: 2-3 giorni

---

### 3. CI/CD Pipeline

**Mancante**: Nessuna automazione GitHub Actions/GitLab CI

**Benefici**:
- Qualità del codice garantita
- Deploy automatico
- Feedback rapido su PR
- Riduzione errori manuali

**Implementare**:

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -r requirements.txt
      - name: Ruff check
        run: ruff check src/
      - name: Ruff format check
        run: ruff format --check src/

  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - name: MyPy check
        run: mypy src/ --strict

  test:
    runs-on: ubuntu-latest
    services:
      qdrant:
        image: qdrant/qdrant:v1.7.0
        ports:
          - 6333:6333
      opensearch:
        image: opensearchproject/opensearch:2.11.0
        ports:
          - 9200:9200
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/ --cov=src/ --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  build:
    runs-on: ubuntu-latest
    needs: [lint, type-check, test]
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t rag-gestionale:${{ github.sha }} .
      - name: Push to registry
        if: github.ref == 'refs/heads/main'
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker push rag-gestionale:${{ github.sha }}

  deploy:
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to production
        run: |
          # Trigger deployment (Kubernetes, Docker Swarm, etc.)
```

**Stima**: 1-2 giorni

---

### 4. Monitoring & Observability

**Attuale**: Solo logging basico con loguru

**Problemi**:
- Nessuna visibilità su performance
- Difficile debugging problemi produzione
- No alerting su errori

**Aggiungere**:

#### 4.1 Prometheus Metrics
```python
# Usare prometheus-fastapi-instrumentator
from prometheus_fastapi_instrumentator import Instrumentator

instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

# Custom metrics
from prometheus_client import Counter, Histogram

search_requests = Counter('search_requests_total', 'Total search requests')
search_latency = Histogram('search_latency_seconds', 'Search latency')
llm_tokens_used = Counter('llm_tokens_used_total', 'Total LLM tokens used')
```

#### 4.2 Grafana Dashboards
- Request rate & latency
- Error rate by endpoint
- Database query performance
- LLM usage & costs
- Cache hit rate
- Queue lengths

#### 4.3 Health Probes
```python
@app.get("/health/liveness")
async def liveness():
    """Kubernetes liveness probe"""
    return {"status": "alive"}

@app.get("/health/readiness")
async def readiness():
    """Kubernetes readiness probe - check dependencies"""
    checks = {
        "qdrant": await check_qdrant(),
        "opensearch": await check_opensearch(),
        "openai": await check_openai(),
    }

    if all(checks.values()):
        return {"status": "ready", "checks": checks}
    else:
        raise HTTPException(status_code=503, detail=checks)
```

#### 4.4 Error Tracking
```python
# Integrare Sentry
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    environment=settings.environment,
)
```

#### 4.5 Distributed Tracing
```python
# OpenTelemetry per tracciare richieste attraverso i servizi
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = trace.get_tracer(__name__)

FastAPIInstrumentor.instrument_app(app)
```

**Stima**: 2-3 giorni

---

## PRIORITÀ MEDIA 🟡

### 5. Caching Layer

**Beneficio**: Ridurre latenza (50-90%) e costi OpenAI (30-50%)

**Problema Attuale**:
- Ogni ricerca ricalcola embeddings
- Risposte LLM non cachate
- Query duplicate costano soldi

**Implementare**:

#### 5.1 Redis Cache
```python
# Cache embeddings
import redis.asyncio as redis
from functools import wraps

redis_client = redis.from_url(settings.redis_url)

async def cache_embeddings(text: str) -> list[float]:
    cache_key = f"emb:{hash(text)}"

    # Check cache
    cached = await redis_client.get(cache_key)
    if cached:
        return pickle.loads(cached)

    # Generate & cache
    embedding = await generate_embedding(text)
    await redis_client.setex(cache_key, 3600, pickle.dumps(embedding))
    return embedding
```

#### 5.2 LLM Response Cache
```python
# Cache risposte LLM per query simili
async def cached_llm_generate(query: str, context: str) -> str:
    cache_key = f"llm:{hashlib.sha256(f'{query}:{context}'.encode()).hexdigest()}"

    cached = await redis_client.get(cache_key)
    if cached:
        logger.info("llm_cache_hit")
        return cached.decode()

    response = await llm_client.generate(query, context)
    await redis_client.setex(cache_key, settings.llm_cache_ttl, response.encode())
    return response
```

#### 5.3 Cache Warming
```python
# Pre-popolare cache con query frequenti
async def warm_cache():
    top_queries = await get_top_queries(limit=100)
    for query in top_queries:
        await cache_embeddings(query)
```

#### 5.4 Cache Invalidation
```python
# Invalidare cache quando documenti cambiano
async def on_document_ingested(doc_id: str):
    # Invalidare cache embeddings correlati
    await redis_client.delete_pattern(f"emb:*{doc_id}*")
    await redis_client.delete_pattern(f"llm:*{doc_id}*")
```

**Configurazione**:
```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
```

**Stima**: 2 giorni

---

### 6. Admin Dashboard

**Mancante**: Nessuna UI amministrativa

**Funzionalità Necessarie**:

#### 6.1 Statistiche Real-Time
- Richieste al minuto/ora/giorno
- Latenza media/p95/p99
- Error rate
- Costo LLM giornaliero/mensile
- Storage utilizzato (Qdrant, OpenSearch, immagini)

#### 6.2 Gestione Chunks
```python
# Endpoints admin
@router.get("/admin/chunks")
async def list_chunks(
    page: int = 1,
    per_page: int = 50,
    search: str | None = None,
    module: str | None = None,
):
    """Lista paginata chunks con filtri"""
    ...

@router.put("/admin/chunks/{chunk_id}")
async def update_chunk(chunk_id: str, update: ChunkUpdate):
    """Modifica contenuto chunk"""
    ...

@router.delete("/admin/chunks/bulk")
async def bulk_delete_chunks(chunk_ids: list[str]):
    """Elimina multipli chunks"""
    ...

@router.post("/admin/chunks/{chunk_id}/reindex")
async def reindex_chunk(chunk_id: str):
    """Rigenera embeddings per chunk"""
    ...
```

#### 6.3 Monitoring Ingestion
```python
# Tracciare job ingestion
@router.get("/admin/ingestion/jobs")
async def list_ingestion_jobs():
    """Lista job di ingestion con stato"""
    return {
        "jobs": [
            {
                "job_id": "abc123",
                "status": "running",  # pending, running, completed, failed
                "urls": ["https://..."],
                "chunks_processed": 150,
                "chunks_total": 300,
                "started_at": "2025-10-16T10:00:00Z",
                "elapsed_seconds": 120,
            }
        ]
    }

@router.post("/admin/ingestion/jobs/{job_id}/cancel")
async def cancel_ingestion_job(job_id: str):
    """Cancella job in corso"""
    ...
```

#### 6.4 Analytics Ricerche
```python
# Query più frequenti
@router.get("/admin/analytics/top-queries")
async def top_queries(days: int = 7, limit: int = 20):
    """Query più cercate con frequenza"""
    ...

# Confidence distribution
@router.get("/admin/analytics/confidence-distribution")
async def confidence_distribution(days: int = 7):
    """Distribuzione confidence score delle risposte"""
    ...

# Module popularity
@router.get("/admin/analytics/module-usage")
async def module_usage(days: int = 30):
    """Utilizzo per modulo (Contabilità, Magazzino, etc.)"""
    ...
```

#### 6.5 Configurazione Dinamica
```python
# Modificare parametri retrieval senza restart
@router.put("/admin/config/retrieval")
async def update_retrieval_config(config: RetrievalSettings):
    """Aggiorna parametri retrieval in runtime"""
    settings.retrieval = config
    # Notificare tutti i worker
    await broadcast_config_change()
```

**Implementazione UI**:
- Streamlit admin page separata (protetta da password)
- Oppure React dashboard con API REST
- Grafici interattivi con Plotly/Chart.js

**Stima**: 4-5 giorni

---

### 7. Versioning & Audit Trail

**Problema**: Nessuna tracciabilità delle modifiche

**Implementare**:

#### 7.1 Document Versioning
```python
# Schema database (PostgreSQL/SQLite)
CREATE TABLE document_versions (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    version_number INT NOT NULL,
    source_url TEXT,
    content_hash VARCHAR(64),
    ingested_at TIMESTAMP DEFAULT NOW(),
    ingested_by VARCHAR(100),  -- API key o user identifier
    metadata JSONB,
    UNIQUE(document_id, version_number)
);

CREATE TABLE chunk_versions (
    id SERIAL PRIMARY KEY,
    chunk_id VARCHAR(255) NOT NULL,
    document_version_id INT REFERENCES document_versions(id),
    version_number INT NOT NULL,
    content TEXT,
    content_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(chunk_id, version_number)
);
```

#### 7.2 Change Tracking
```python
@router.put("/chunks/{chunk_id}")
async def update_chunk(chunk_id: str, update: ChunkUpdate, user: str = Depends(get_current_user)):
    """Modifica chunk con versioning"""

    # Recupera versione corrente
    current = await get_chunk(chunk_id)

    # Crea nuova versione
    new_version = await create_chunk_version(
        chunk_id=chunk_id,
        content=update.content,
        changed_by=user,
        change_reason=update.reason,
    )

    # Aggiorna chunk corrente
    await update_chunk_content(chunk_id, update.content)

    # Log audit
    await log_audit_event(
        event_type="chunk_updated",
        chunk_id=chunk_id,
        version=new_version,
        user=user,
        changes=compute_diff(current.content, update.content),
    )
```

#### 7.3 Rollback Capabilities
```python
@router.post("/chunks/{chunk_id}/rollback")
async def rollback_chunk(chunk_id: str, to_version: int):
    """Ripristina chunk a versione precedente"""

    # Recupera versione target
    target_version = await get_chunk_version(chunk_id, to_version)

    # Crea nuova versione con contenuto vecchio
    await create_chunk_version(
        chunk_id=chunk_id,
        content=target_version.content,
        changed_by="system",
        change_reason=f"Rollback to version {to_version}",
    )

    # Aggiorna chunk
    await update_chunk_content(chunk_id, target_version.content)

    # Rigenera embeddings
    await reindex_chunk(chunk_id)
```

#### 7.4 Audit Log Query
```python
@router.get("/admin/audit-log")
async def get_audit_log(
    event_type: str | None = None,
    user: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 100,
):
    """Query audit log con filtri"""
    ...
```

**Stima**: 3-4 giorni

---

### 8. Performance Optimization

**Ottimizzazioni Concrete**:

#### 8.1 Connection Pooling
```python
# Qdrant connection pool
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

class QdrantPool:
    def __init__(self, host: str, port: int, pool_size: int = 10):
        self._clients = [
            QdrantClient(host=host, port=port, timeout=30)
            for _ in range(pool_size)
        ]
        self._available = asyncio.Queue()
        for client in self._clients:
            self._available.put_nowait(client)

    async def get_client(self) -> QdrantClient:
        return await self._available.get()

    async def return_client(self, client: QdrantClient):
        await self._available.put(client)

# Usage
qdrant_pool = QdrantPool(host=settings.qdrant_host, port=settings.qdrant_port)

async def search_vectors(query_vector: list[float]):
    client = await qdrant_pool.get_client()
    try:
        results = await client.search(...)
        return results
    finally:
        await qdrant_pool.return_client(client)
```

#### 8.2 Batch Embedding Generation
```python
# Invece di generare embeddings uno alla volta
async def batch_generate_embeddings(texts: list[str], batch_size: int = 32):
    """Genera embeddings in batch per efficienza"""
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        # GPU utilization migliore con batch
        embeddings = await embedding_model.encode_async(batch)
        all_embeddings.extend(embeddings)

    return all_embeddings
```

#### 8.3 Async Database Operations
```python
# Parallelizzare chiamate a Qdrant e OpenSearch
async def hybrid_search(query: str, k: int = 10):
    query_embedding = await generate_embedding(query)

    # Esegui in parallelo
    vector_results, lexical_results = await asyncio.gather(
        search_qdrant(query_embedding, k),
        search_opensearch(query, k),
    )

    # Combina risultati
    return combine_results(vector_results, lexical_results)
```

#### 8.4 Response Compression
```python
# Abilitare gzip compression
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

#### 8.5 Lazy Loading Chunks
```python
# Non caricare tutto il chunk in memoria se non necessario
class ChunkProxy:
    def __init__(self, chunk_id: str):
        self.chunk_id = chunk_id
        self._content: str | None = None

    async def get_content(self) -> str:
        if self._content is None:
            self._content = await load_chunk_content(self.chunk_id)
        return self._content

# Usage in search
results = [ChunkProxy(chunk_id) for chunk_id in search_results]
# Content loaded solo quando necessario
```

#### 8.6 Query Result Caching
```python
# Cache risultati ricerca per query identiche
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def search_cache_key(query: str, filters: str) -> str:
    return hashlib.sha256(f"{query}:{filters}".encode()).hexdigest()

async def cached_search(query: str, filters: dict):
    cache_key = search_cache_key(query, json.dumps(filters, sort_keys=True))

    cached = await redis_client.get(f"search:{cache_key}")
    if cached:
        return json.loads(cached)

    results = await perform_search(query, filters)
    await redis_client.setex(f"search:{cache_key}", 300, json.dumps(results))
    return results
```

**Benefici Attesi**:
- Latenza ridotta del 40-60%
- Throughput aumentato del 100-200%
- Utilizzo memoria ottimizzato
- Costi OpenAI ridotti del 30-50%

**Stima**: 3-4 giorni

---

### 9. Documentazione API

**Mancante**: Documentazione Swagger/Scalar non configurata correttamente

**Implementare**:

#### 9.1 OpenAPI Schema Completo
```python
# api/main.py
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="RAG Gestionale API",
    version="1.0.0",
    description="""
    Sistema RAG per ricerca semantica su manuali gestionali.

    ## Funzionalità

    * **Search**: Ricerca ibrida semantica + lessicale con reranking
    * **Ingest**: Ingestion automatica da URL o directory
    * **Chunks**: Gestione chunks con metadata
    * **Images**: Serving immagini estratte con OCR
    * **Health**: Monitoraggio sistema e statistiche

    ## Autenticazione

    Usa header `X-API-Key` per autenticare le richieste.

    ## Rate Limits

    - Search: 10 richieste/minuto
    - Ingest: 5 richieste/ora
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Aggiungi security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }

    # Applica security a tutti gli endpoint
    for path in openapi_schema["paths"].values():
        for operation in path.values():
            operation["security"] = [{"ApiKeyAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

#### 9.2 Request/Response Examples
```python
from pydantic import Field

class SearchRequest(BaseModel):
    query: str = Field(
        ...,
        description="Query di ricerca in linguaggio naturale",
        example="Come faccio a creare una fattura elettronica?",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Numero massimo di risultati da restituire",
        example=5,
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Filtri opzionali per modulo, versione, etc.",
        example={"module": "fatturazione", "version": "2024"},
    )

class SearchResponse(BaseModel):
    answer: str = Field(
        ...,
        description="Risposta generata dal sistema RAG",
        example="Per creare una fattura elettronica...",
    )
    query_type: str = Field(
        ...,
        description="Tipo di query identificato",
        example="PROCEDURE",
    )
    sources: list[SourceChunk] = Field(
        ...,
        description="Chunks utilizzati per generare la risposta",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score di confidenza della risposta",
        example=0.87,
    )
    processing_time_ms: int = Field(
        ...,
        description="Tempo di elaborazione in millisecondi",
        example=450,
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "answer": "Per creare una fattura elettronica segui questi passi...",
                    "query_type": "PROCEDURE",
                    "sources": [
                        {
                            "chunk_id": "abc123",
                            "content": "La fattura elettronica...",
                            "score": 0.92,
                            "metadata": {
                                "title": "Creazione Fatture",
                                "module": "fatturazione",
                            },
                        }
                    ],
                    "confidence": 0.87,
                    "processing_time_ms": 450,
                }
            ]
        }
    }
```

#### 9.3 Error Codes Documentation
```python
# Documentare tutti i possibili errori
from fastapi import status
from fastapi.responses import JSONResponse

class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: dict[str, Any] | None = None

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error_code": "INVALID_INPUT",
            "message": str(exc),
        },
    )

# Documentare nella OpenAPI spec
responses = {
    400: {
        "description": "Invalid input",
        "content": {
            "application/json": {
                "example": {
                    "error_code": "INVALID_INPUT",
                    "message": "Query cannot be empty",
                }
            }
        },
    },
    403: {
        "description": "Invalid API key",
        "content": {
            "application/json": {
                "example": {
                    "error_code": "INVALID_API_KEY",
                    "message": "The provided API key is not valid",
                }
            }
        },
    },
    429: {
        "description": "Rate limit exceeded",
        "content": {
            "application/json": {
                "example": {
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Try again in 60 seconds.",
                }
            }
        },
    },
    503: {
        "description": "Service unavailable",
        "content": {
            "application/json": {
                "example": {
                    "error_code": "SERVICE_UNAVAILABLE",
                    "message": "Vector store is not available",
                }
            }
        },
    },
}

@router.post("/search", responses=responses)
async def search(...):
    ...
```

#### 9.4 Integration Tutorials
```markdown
# docs/API_INTEGRATION.md

## Integrazione API RAG Gestionale

### Quick Start

1. Ottieni una API key dall'amministratore
2. Testa la connessione:

```bash
curl -X GET https://api.example.com/health \
  -H "X-API-Key: your-api-key"
```

3. Effettua una ricerca:

```bash
curl -X POST https://api.example.com/search \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Come creare una fattura?",
    "top_k": 5
  }'
```

### Esempi per Linguaggio

#### Python
```python
import httpx

async def search_rag(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.example.com/search",
            headers={"X-API-Key": "your-api-key"},
            json={"query": query, "top_k": 5},
        )
        return response.json()
```

#### JavaScript
```javascript
async function searchRAG(query) {
  const response = await fetch('https://api.example.com/search', {
    method: 'POST',
    headers: {
      'X-API-Key': 'your-api-key',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query, top_k: 5 }),
  });
  return response.json();
}
```

#### C#
```csharp
using System.Net.Http;
using System.Text.Json;

public async Task<SearchResponse> SearchRAGAsync(string query)
{
    var client = new HttpClient();
    client.DefaultRequestHeaders.Add("X-API-Key", "your-api-key");

    var content = new StringContent(
        JsonSerializer.Serialize(new { query, top_k = 5 }),
        Encoding.UTF8,
        "application/json"
    );

    var response = await client.PostAsync("https://api.example.com/search", content);
    var json = await response.Content.ReadAsStringAsync();
    return JsonSerializer.Deserialize<SearchResponse>(json);
}
```

### Best Practices

1. **Caching**: Casha le risposte per query frequenti
2. **Retry Logic**: Implementa retry con backoff esponenziale
3. **Timeout**: Imposta timeout di 30 secondi
4. **Error Handling**: Gestisci correttamente errori 4xx e 5xx
5. **Rate Limiting**: Rispetta i rate limits (10 req/min)
```

**Stima**: 2 giorni

---

## PRIORITÀ BASSA 🟢

### 10. Features Avanzate

#### 10.1 A/B Testing per Strategie Retrieval
```python
# Testare diverse configurazioni retrieval
@router.post("/search")
async def search(request: SearchRequest, experiment_group: str = Header(default="control")):
    if experiment_group == "variant_a":
        # Usa parametri diversi
        settings.retrieval.top_k_vector = 15
        settings.retrieval.rerank_top_k = 5
    elif experiment_group == "variant_b":
        # Usa diversification più aggressiva
        settings.retrieval.diversification_threshold = 0.85

    results = await perform_search(request.query)

    # Log per analytics
    await log_experiment_result(
        query=request.query,
        experiment_group=experiment_group,
        results=results,
    )

    return results
```

#### 10.2 Export Results
```python
@router.post("/search/export")
async def export_search_results(
    request: SearchRequest,
    format: Literal["json", "csv", "pdf"] = "json",
):
    """Esporta risultati in vari formati"""
    results = await perform_search(request.query)

    if format == "csv":
        return StreamingResponse(
            generate_csv(results),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=results.csv"},
        )
    elif format == "pdf":
        pdf = generate_pdf_report(results)
        return Response(content=pdf, media_type="application/pdf")
    else:
        return results
```

#### 10.3 Batch Processing API
```python
@router.post("/search/batch")
async def batch_search(queries: list[str], background_tasks: BackgroundTasks):
    """Processa multiple query in background"""
    job_id = str(uuid.uuid4())

    background_tasks.add_task(process_batch_queries, job_id, queries)

    return {
        "job_id": job_id,
        "status": "processing",
        "queries_count": len(queries),
        "estimated_completion_seconds": len(queries) * 2,
    }

@router.get("/search/batch/{job_id}")
async def get_batch_results(job_id: str):
    """Recupera risultati batch processing"""
    status = await get_job_status(job_id)
    results = await get_job_results(job_id)

    return {
        "job_id": job_id,
        "status": status,  # processing, completed, failed
        "results": results,
    }
```

#### 10.4 Webhook Notifications
```python
@router.post("/ingest")
async def ingest(
    request: IngestRequest,
    webhook_url: str | None = None,
    background_tasks: BackgroundTasks = None,
):
    """Ingest con notifica webhook al completamento"""
    job_id = await start_ingestion_job(request)

    if webhook_url:
        background_tasks.add_task(
            notify_on_completion,
            job_id,
            webhook_url,
        )

    return {"job_id": job_id}

async def notify_on_completion(job_id: str, webhook_url: str):
    """Invia POST a webhook quando job completo"""
    while True:
        status = await get_job_status(job_id)
        if status in ["completed", "failed"]:
            await httpx.AsyncClient().post(
                webhook_url,
                json={
                    "job_id": job_id,
                    "status": status,
                    "timestamp": datetime.now().isoformat(),
                },
            )
            break
        await asyncio.sleep(5)
```

#### 10.5 Multi-Language Support
```python
# Oltre italiano, supportare altre lingue
LANGUAGE_MODELS = {
    "it": "BAAI/bge-m3",
    "en": "BAAI/bge-m3",
    "fr": "BAAI/bge-m3",
    "de": "BAAI/bge-m3",
}

@router.post("/search")
async def search(request: SearchRequest, language: str = "it"):
    """Ricerca multi-lingua"""
    embedding_model = get_embedding_model(language)
    query_embedding = await embedding_model.encode(request.query)

    # Usa prompt LLM specifico per lingua
    prompt_template = get_prompt_template(language)
    ...
```

**Stima**: 5-7 giorni totali

---

### 11. User Experience Improvements

#### 11.1 Feedback Loop
```python
# Raccogliere feedback utenti su risposte
@router.post("/search/{search_id}/feedback")
async def submit_feedback(
    search_id: str,
    feedback: Literal["positive", "negative"],
    comment: str | None = None,
):
    """Thumbs up/down su risposta"""
    await store_feedback(
        search_id=search_id,
        feedback=feedback,
        comment=comment,
        timestamp=datetime.now(),
    )

    # Usa feedback per fine-tuning futuro
    if feedback == "negative":
        await flag_for_review(search_id)

    return {"status": "feedback_recorded"}
```

#### 11.2 Query Suggestions/Autocomplete
```python
@router.get("/search/suggestions")
async def get_suggestions(prefix: str, limit: int = 10):
    """Autocomplete query basato su storico"""
    # Usa Trie o Redis per suggestions veloci
    suggestions = await query_autocomplete.get_suggestions(prefix, limit)

    return {
        "suggestions": [
            {
                "text": "Come creare una fattura",
                "frequency": 125,
                "avg_confidence": 0.87,
            },
            ...
        ]
    }
```

#### 11.3 Search History
```python
@router.get("/search/history")
async def get_search_history(
    user_id: str = Depends(get_current_user),
    limit: int = 20,
):
    """Storico ricerche utente"""
    history = await get_user_search_history(user_id, limit)

    return {
        "searches": [
            {
                "query": "Come creare fattura",
                "timestamp": "2025-10-16T10:30:00Z",
                "confidence": 0.87,
            },
            ...
        ]
    }

@router.post("/search/{search_id}/bookmark")
async def bookmark_search(search_id: str, user_id: str = Depends(get_current_user)):
    """Salva ricerca nei preferiti"""
    await add_bookmark(user_id, search_id)
    return {"status": "bookmarked"}
```

#### 11.4 Dark Mode Streamlit
```python
# streamlit_app.py
import streamlit as st

# Theme configuration
st.set_page_config(
    page_title="RAG Gestionale",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS custom per dark mode
st.markdown("""
<style>
    .stApp {
        background-color: var(--background-color);
    }
    .stTextInput > div > div > input {
        background-color: var(--secondary-background-color);
    }
</style>
""", unsafe_allow_html=True)

# Toggle theme
theme = st.sidebar.selectbox("Theme", ["Light", "Dark"])
if theme == "Dark":
    st.markdown("""
    <style>
        :root {
            --background-color: #0e1117;
            --secondary-background-color: #262730;
            --text-color: #fafafa;
        }
    </style>
    """, unsafe_allow_html=True)
```

#### 11.5 Advanced Search Filters UI
```python
# Streamlit UI migliorata
with st.sidebar:
    st.header("Filtri Avanzati")

    modules = st.multiselect(
        "Moduli",
        options=["Contabilità", "Fatturazione", "Magazzino", "HR", "CRM"],
        default=[],
    )

    versions = st.multiselect(
        "Versioni",
        options=["2024", "2023", "2022"],
        default=["2024"],
    )

    content_types = st.multiselect(
        "Tipo Contenuto",
        options=["procedure", "parameters", "errors", "screenshots"],
        default=[],
    )

    date_range = st.date_input(
        "Range Date Ingestion",
        value=None,
    )

    min_confidence = st.slider(
        "Confidenza Minima",
        min_value=0.0,
        max_value=1.0,
        value=0.5,
        step=0.05,
    )

# Passa filtri all'API
filters = {
    "modules": modules,
    "versions": versions,
    "content_types": content_types,
    "min_confidence": min_confidence,
}

results = await api_client.search(query, filters=filters)
```

**Stima**: 4-5 giorni totali

---

### 12. Scalabilità Enterprise

#### 12.1 Multi-Tenancy Support
```python
# Separazione per cliente/tenant
class TenantSettings(BaseModel):
    tenant_id: str
    qdrant_collection: str  # gestionale_docs_tenant_abc
    opensearch_index: str   # gestionale_lexical_tenant_abc
    api_rate_limit: int
    storage_quota_gb: int

@router.post("/search")
async def search(
    request: SearchRequest,
    tenant: TenantSettings = Depends(get_tenant_from_api_key),
):
    """Ricerca isolata per tenant"""
    retriever = HybridRetriever(
        collection_name=tenant.qdrant_collection,
        index_name=tenant.opensearch_index,
    )

    results = await retriever.search(request.query)
    return results
```

#### 12.2 Sharding Qdrant Collections
```python
# Per dataset molto grandi, shard per modulo
COLLECTION_SHARDS = {
    "contabilita": "gestionale_docs_contabilita",
    "fatturazione": "gestionale_docs_fatturazione",
    "magazzino": "gestionale_docs_magazzino",
}

async def multi_collection_search(query: str, modules: list[str]):
    """Cerca su multiple collections in parallelo"""
    tasks = []
    for module in modules:
        collection = COLLECTION_SHARDS[module]
        tasks.append(search_collection(query, collection))

    results = await asyncio.gather(*tasks)
    return merge_and_rerank(results)
```

#### 12.3 Load Balancing
```yaml
# Kubernetes deployment con HPA
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rag-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rag-api
  template:
    metadata:
      labels:
        app: rag-api
    spec:
      containers:
      - name: rag-api
        image: rag-gestionale:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health/liveness
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/readiness
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rag-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rag-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### 12.4 Async Task Queue
```python
# Usare Celery per task pesanti
from celery import Celery

celery_app = Celery('rag_gestionale', broker='redis://localhost:6379/0')

@celery_app.task
def ingest_large_document(url: str, tenant_id: str):
    """Task asincrono per ingestion pesante"""
    coordinator = IngestionCoordinator(tenant_id=tenant_id)
    result = coordinator.ingest_url(url)

    # Notifica completamento
    notify_completion(tenant_id, result)

    return result

# API endpoint
@router.post("/ingest/async")
async def ingest_async(request: IngestRequest):
    """Ingestion asincrona via Celery"""
    task = ingest_large_document.delay(request.url, request.tenant_id)

    return {
        "task_id": task.id,
        "status": "queued",
        "check_status_url": f"/tasks/{task.id}",
    }
```

**Stima**: 5-7 giorni totali

---

## 🚀 Quick Wins (Implementabili Subito)

### A. Configurare Swagger UI ✅
**Tempo**: 10 minuti

```python
# api/main.py
app = FastAPI(
    title="RAG Gestionale API",
    version="1.0.0",
    description="Sistema RAG per ricerca semantica su manuali gestionali",
    docs_url="/docs",
    redoc_url="/redoc",
)
```

Accedi a: `http://localhost:8000/docs`

---

### B. Aggiungere Logging Strutturato ✅
**Tempo**: 30 minuti

```python
# Migliorare loguru con JSON output
from loguru import logger
import sys

logger.remove()
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    level="INFO",
    serialize=True,  # JSON output
)

# Usage
logger.bind(
    request_id=request_id,
    user_id=user_id,
    query=query,
).info("search_request")
```

---

### C. Health Endpoint Migliorato ✅
**Tempo**: 1 ora

```python
@router.get("/health/readiness")
async def readiness_check():
    """Check dipendenze"""
    checks = {}

    # Check Qdrant
    try:
        await vector_store.client.get_collections()
        checks["qdrant"] = "healthy"
    except Exception as e:
        checks["qdrant"] = f"unhealthy: {e}"

    # Check OpenSearch
    try:
        await lexical_search.client.ping()
        checks["opensearch"] = "healthy"
    except Exception as e:
        checks["opensearch"] = f"unhealthy: {e}"

    # Check OpenAI
    if settings.llm.enabled:
        try:
            await llm_client.health_check()
            checks["openai"] = "healthy"
        except Exception as e:
            checks["openai"] = f"unhealthy: {e}"

    all_healthy = all("healthy" in v for v in checks.values())

    if all_healthy:
        return {"status": "ready", "checks": checks}
    else:
        raise HTTPException(status_code=503, detail=checks)
```

---

### D. Request ID Tracking ✅
**Tempo**: 30 minuti

```python
import uuid
from fastapi import Request

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Aggiungi a response headers
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response

# Usage nei log
@router.post("/search")
async def search(request: Request, ...):
    logger.bind(request_id=request.state.request_id).info("search_start")
    ...
```

---

### E. Environment Validation ✅
**Tempo**: 1 ora

```python
# scripts/preflight_check.py
import sys
from rag_gestionale.config.settings import settings

def check_qdrant():
    """Verifica connessione Qdrant"""
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host=settings.vector_store.host, port=settings.vector_store.port)
        client.get_collections()
        print("✓ Qdrant: OK")
        return True
    except Exception as e:
        print(f"✗ Qdrant: FAILED - {e}")
        return False

def check_opensearch():
    """Verifica connessione OpenSearch"""
    try:
        from opensearchpy import OpenSearch
        client = OpenSearch(
            hosts=[{"host": settings.lexical_search.host, "port": settings.lexical_search.port}]
        )
        client.ping()
        print("✓ OpenSearch: OK")
        return True
    except Exception as e:
        print(f"✗ OpenSearch: FAILED - {e}")
        return False

def check_openai():
    """Verifica API key OpenAI"""
    if not settings.llm.enabled:
        print("⊘ OpenAI: DISABLED")
        return True

    try:
        import openai
        openai.api_key = settings.llm.api_key
        # Test API key
        openai.Model.list()
        print("✓ OpenAI: OK")
        return True
    except Exception as e:
        print(f"✗ OpenAI: FAILED - {e}")
        return False

def main():
    print("=== Preflight Check ===\n")

    checks = [
        check_qdrant(),
        check_opensearch(),
        check_openai(),
    ]

    if all(checks):
        print("\n✓ All checks passed!")
        sys.exit(0)
    else:
        print("\n✗ Some checks failed. Fix issues before starting.")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

Uso: `python scripts/preflight_check.py`

---

## 📋 Riepilogo Priorità

### Implementare SUBITO (1-2 settimane)
1. ✅ Quick wins (A-E) - **2-3 giorni**
2. 🔴 Test suite - **3-5 giorni**
3. 🔴 Sicurezza base (CORS, API key auth) - **2 giorni**

### Implementare PRESTO (1 mese)
4. 🔴 CI/CD pipeline - **2 giorni**
5. 🔴 Monitoring (Prometheus + Grafana) - **3 giorni**
6. 🟡 Caching layer (Redis) - **2 giorni**
7. 🟡 Performance optimization - **3 giorni**

### Implementare DOPO (2-3 mesi)
8. 🟡 Admin dashboard - **5 giorni**
9. 🟡 Versioning & audit trail - **4 giorni**
10. 🟡 Documentazione API completa - **2 giorni**
11. 🟢 Features avanzate - **5-7 giorni**
12. 🟢 UX improvements - **5 giorni**
13. 🟢 Scalabilità enterprise - **7 giorni**

---

## 💰 ROI Stimato per Area

| Area | Effort | Impact | ROI |
|------|--------|--------|-----|
| Test Suite | 5d | ⭐⭐⭐⭐⭐ | Alto |
| Sicurezza | 2d | ⭐⭐⭐⭐⭐ | Altissimo |
| CI/CD | 2d | ⭐⭐⭐⭐ | Alto |
| Monitoring | 3d | ⭐⭐⭐⭐⭐ | Altissimo |
| Caching | 2d | ⭐⭐⭐⭐⭐ | Altissimo |
| Performance | 3d | ⭐⭐⭐⭐ | Alto |
| Admin Dashboard | 5d | ⭐⭐⭐ | Medio |
| Versioning | 4d | ⭐⭐ | Basso |
| Docs API | 2d | ⭐⭐⭐ | Medio |
| Features Avanzate | 7d | ⭐⭐ | Basso |
| UX Improvements | 5d | ⭐⭐⭐ | Medio |
| Scalabilità | 7d | ⭐⭐ | Basso* |

*Basso se non hai bisogno immediato di scale

---

## 🎯 Prossimi Passi Consigliati

1. **Implementare Quick Wins** (A-E) - Visibilità immediata
2. **Aggiungere Test Suite** - Fondamenta solide
3. **Fixare Sicurezza** - Bloccare vulnerabilità
4. **Setup CI/CD** - Automazione deployment
5. **Aggiungere Monitoring** - Visibilità produzione

Dopo questi 5 step, il sistema sarà **production-ready** per deployment enterprise.

---

## 📚 Risorse Utili

- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Qdrant Performance Tuning](https://qdrant.tech/documentation/guides/optimize/)
- [OpenSearch Optimization](https://opensearch.org/docs/latest/tuning-your-cluster/)
- [RAG Production Patterns](https://www.anthropic.com/research/retrieval-augmented-generation)
- [Testing FastAPI](https://fastapi.tiangolo.com/tutorial/testing/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)

---

**Documento creato**: 2025-10-16
**Versione**: 1.0
**Autore**: Claude Code (Anthropic)
