# RAG Gestionale - Sistema di Retrieval Augmented Generation per Documentazione Gestionali

Sistema RAG (Retrieval Augmented Generation) specializzato per documentazione di software gestionali in italiano. Combina ricerca semantica, lessicale e generazione intelligente con LLM per fornire risposte precise e contestualizzate.

## 🚀 Caratteristiche Principali

### 🔍 Ricerca Ibrida Avanzata
- **Ricerca Semantica**: Embeddings multilingua con BAAI/bge-m3
- **Ricerca Lessicale**: BM25 ottimizzato per termini tecnici italiani
- **Cross-Encoder Reranking**: BAAI/bge-reranker-large per ordinamento ottimale
- **Fusione Intelligente**: Reciprocal Rank Fusion (RRF) per combinare risultati

### 🤖 Generazione con LLM
- **Integrazione OpenAI**: GPT-4o-mini per risposte naturali e precise
- **Template Tipizzati**: Risposte strutturate per parametri, procedure ed errori
- **Anti-Hallucination**: Citazioni obbligatorie e verifica consistenza con fonti
- **Modalità Ibrida**: Scelta automatica tra template e LLM basata su complessità

### 📚 Gestione Documentazione
- **Chunking Gerarchico**: Parent/child chunks con overlap configurabile
- **Metadati Ricchi**: Moduli, versioni, breadcrumbs, UI paths
- **Deduplicazione**: Rimozione automatica contenuti duplicati (soglia 92%)
- **Multi-formato**: Supporto HTML, PDF, Markdown

### 🎯 Query Classification
- **Tipizzazione Automatica**: Classificazione query in categorie
  - `PARAMETER`: Impostazioni e configurazioni
  - `PROCEDURE`: Guide passo-passo
  - `ERROR`: Risoluzione problemi
  - `GENERAL`: Informazioni generali

### 🔧 API REST Moderna
- **FastAPI Framework**: Performance e documentazione automatica
- **Scalar + Swagger**: Doppia documentazione interattiva
- **Routers Modulari**: Organizzazione pulita degli endpoint
- **CORS Configurabile**: Integrazione frontend facilitata

## 📋 Prerequisiti

- Python 3.9+
- Qdrant Vector Database
- OpenSearch
- OpenAI API Key (per funzionalità LLM)

## 🛠️ Installazione

### 1. Clona il repository
```bash
git clone https://github.com/yourusername/rag-gestionale.git
cd rag-gestionale
```

### 2. Crea ambiente virtuale
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Installa dipendenze con UV
```bash
pip install uv
uv pip install -r requirements.txt
```

### 4. Configura ambiente
Copia `.env.example` in `.env` e configura:

```env
# API
RAG_API_HOST=0.0.0.0
RAG_API_PORT=8000

# Vector Store (Qdrant)
RAG_VECTOR_STORE__HOST=localhost
RAG_VECTOR_STORE__PORT=6333
RAG_VECTOR_STORE__COLLECTION_NAME=gestionale_docs

# Lexical Search (OpenSearch)
RAG_LEXICAL_SEARCH__HOST=localhost
RAG_LEXICAL_SEARCH__PORT=9200
RAG_LEXICAL_SEARCH__INDEX_NAME=gestionale_lexical

# LLM Configuration (OpenAI)
RAG_LLM__ENABLED=true
RAG_LLM__API_KEY=your-openai-api-key
RAG_LLM__MODEL_NAME=gpt-4o-mini
RAG_LLM__TEMPERATURE=0.2

# Generation Settings
RAG_GENERATION__GENERATION_MODE=hybrid
```

### 5. Avvia servizi dipendenti

#### Docker Compose (consigliato)
```bash
docker-compose up -d
```

#### Oppure manualmente:
```bash
# Qdrant
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant

# OpenSearch
docker run -d -p 9200:9200 -p 9600:9600 \
  -e "discovery.type=single-node" \
  -e "DISABLE_SECURITY_PLUGIN=true" \
  opensearchproject/opensearch:latest
```

## 🚀 Avvio

### Server API
```bash
python -m src.rag_gestionale.api.main
```

L'API sarà disponibile su:
- Homepage: http://localhost:8000
- Scalar Docs: http://localhost:8000/docs
- Swagger UI: http://localhost:8000/swagger

### Interfaccia Streamlit (opzionale)
```bash
streamlit run streamlit_app.py
```

## 📡 API Endpoints

### 🔍 Ricerca
```http
POST /search
Content-Type: application/json

{
  "query": "Come impostare aliquota IVA predefinita?",
  "filters": {"module": "Contabilità"},
  "top_k": 5,
  "include_sources": true
}
```

**Risposta:**
```json
{
  "query": "Come impostare aliquota IVA predefinita?",
  "query_type": "PARAMETER",
  "answer": "Per impostare l'aliquota IVA predefinita...",
  "sources": [...],
  "confidence": 0.85,
  "processing_time_ms": 450
}
```

### 📥 Ingestione
```http
POST /ingest
Content-Type: application/json

{
  "urls": ["https://docs.example.com/guide"],
  "directory": "/path/to/docs"
}
```

### 💚 Health Check
```http
GET /health
```

### 📊 Statistiche
```http
GET /stats
```

### 📄 Gestione Chunks
```http
GET /chunks/{chunk_id}
DELETE /chunks/{chunk_id}
```

## 🏗️ Architettura

```
src/rag_gestionale/
├── api/
│   ├── main.py              # FastAPI app principale
│   ├── dependencies.py       # Dependency injection
│   └── routers/             # Endpoints modulari
│       ├── search.py        # Ricerca RAG
│       ├── ingest.py        # Ingestione documenti
│       ├── chunks.py        # Gestione chunks
│       └── health.py        # Health & stats
├── core/
│   ├── models.py            # Modelli Pydantic
│   └── utils.py             # Utility generali
├── config/
│   └── settings.py          # Configurazione centralizzata
├── ingest/
│   ├── coordinator.py       # Orchestrazione ingestione
│   ├── crawler.py           # Web crawling
│   ├── pdf_parser.py        # Parsing PDF
│   ├── html_parser.py       # Parsing HTML
│   └── chunker.py           # Chunking gerarchico
├── retrieval/
│   ├── hybrid_retriever.py  # Retrieval ibrido
│   ├── vector_store.py      # Qdrant integration
│   └── lexical_search.py    # OpenSearch BM25
└── generation/
    ├── generator.py         # Response generation
    ├── templates.py         # Template system
    └── llm_client.py        # OpenAI client
```

## 🔧 Configurazione Avanzata

### Chunking Parameters
```python
# settings.py o .env
PARENT_MAX_TOKENS=800        # Token massimi per parent chunk
CHILD_PROC_MAX_TOKENS=350    # Token per chunk procedurali
CHILD_PARAM_MAX_TOKENS=200   # Token per chunk parametri
```

### Retrieval Tuning
```python
K_DENSE=40        # Candidati ricerca semantica
K_LEXICAL=20      # Candidati ricerca lessicale
K_RERANK=30       # Candidati per reranking
K_FINAL=10        # Risultati finali
```

### LLM Settings
```python
LLM_MODEL_NAME="gpt-4o-mini"     # Modello OpenAI
LLM_TEMPERATURE=0.2               # Creatività risposte
LLM_MAX_TOKENS=1500              # Lunghezza massima
MAX_REQUESTS_PER_MINUTE=20       # Rate limiting
```

## 📚 Esempi d'Uso

### Python Client
```python
import requests

# Ricerca
response = requests.post(
    "http://localhost:8000/search",
    json={
        "query": "errore E001 fatturazione",
        "top_k": 3
    }
)
result = response.json()
print(f"Risposta: {result['answer']}")
print(f"Confidenza: {result['confidence']}")

# Ingestione
response = requests.post(
    "http://localhost:8000/ingest",
    json={
        "urls": ["https://docs.gestionale.it/guide"]
    }
)
```

### CLI Usage
```bash
# Ricerca da CLI
python -m src.rag_gestionale.api.cli search "come configurare fattura elettronica"

# Ingestione directory
python -m src.rag_gestionale.api.cli ingest --directory ./docs
```

## 🧪 Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Coverage report
pytest --cov=src/rag_gestionale --cov-report=html
```

## 🔍 Monitoring

### Metriche disponibili
- **Retrieval Stats**: Precision, recall, latency
- **Ingestion Stats**: Documenti processati, chunk creati
- **LLM Usage**: Token utilizzati, costi stimati

### Logging
Configurabile via `RAG_LOG_LEVEL`:
- `DEBUG`: Dettagli completi
- `INFO`: Operazioni normali
- `WARNING`: Situazioni anomale
- `ERROR`: Errori recuperabili

## 🚀 Performance

### Ottimizzazioni implementate
- **Batch Processing**: Embeddings e ingestione
- **Async I/O**: Operazioni database parallele
- **Connection Pooling**: Riuso connessioni DB
- **HNSW Index**: Ricerca vettoriale veloce

### Benchmark tipici
- Ricerca semantica: ~200ms (10k documenti)
- Generazione LLM: ~2-3s
- Ingestione: ~100 docs/minuto

## 🔒 Sicurezza

- **API Key Protection**: Autenticazione endpoint sensibili
- **CORS Configuration**: Domini autorizzati
- **Input Validation**: Pydantic models
- **SQL Injection Prevention**: Query parametrizzate
- **Rate Limiting**: Protezione DoS

## 📝 Contribuire

1. Fork del repository
2. Crea branch feature (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Apri Pull Request

### Guidelines
- Segui PEP 8
- Usa type hints
- Scrivi docstrings
- Aggiungi test per nuove feature
- Formatta con `ruff format`

## 📄 Licenza

Distribuito sotto licenza MIT. Vedi `LICENSE` per maggiori informazioni.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Qdrant](https://qdrant.tech/) - Vector database
- [OpenSearch](https://opensearch.org/) - Search engine
- [OpenAI](https://openai.com/) - LLM provider
- [Sentence Transformers](https://www.sbert.net/) - Embeddings

## 📧 Contatti

Per domande o supporto:
- Email: support@example.com
- Issues: [GitHub Issues](https://github.com/yourusername/rag-gestionale/issues)

---
Built with ❤️ for Italian enterprise software documentation