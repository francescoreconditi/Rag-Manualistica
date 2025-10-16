# Analisi CUDA/GPU Optimization per RAG System

## 1. Componenti Ottimizzabili con CUDA

### 1.1 Embedding Generation (PRIORITÀ ALTA)
**File**: `src/rag_gestionale/retrieval/vector_store.py`

**Bottleneck attuale**:
- Linea 60: `device="cpu"` hardcoded
- Metodo `_generate_embeddings_batch()` (linee 191-213): processa batch di testi
- Utilizzo: sia durante ingest (migliaia di chunk) che durante query (1 query alla volta)

**Impatto stimato**: 10-50x speedup
- Ingest di 1000 chunk: da ~2-3 minuti a ~10-30 secondi
- Query embedding: da ~50-100ms a ~5-10ms

**Modifiche necessarie**:
```python
# Linea 60 - vector_store.py
self.embedding_model = SentenceTransformer(
    self.settings.embedding.model_name,
    device="cuda" if torch.cuda.is_available() else "cpu",
)
```

### 1.2 Cross-Encoder Reranking (PRIORITÀ ALTA)
**File**: `src/rag_gestionale/retrieval/hybrid_retriever.py`

**Bottleneck attuale**:
- Linea 94: CrossEncoder senza device specification
- Metodo `rerank()` (linee 229-252): processa 20-50 coppie query-documento per ricerca

**Impatto stimato**: 5-20x speedup
- Reranking 50 risultati: da ~200-400ms a ~20-50ms

**Modifiche necessarie**:
```python
# Linea 94 - hybrid_retriever.py
self.reranker = CrossEncoder(
    self.settings.reranker.model_name,
    max_length=self.settings.reranker.max_length,
    device="cuda" if torch.cuda.is_available() else "cpu",
)
```

### 1.3 Batch Processing durante Ingest (PRIORITÀ MEDIA)
**File**: `src/rag_gestionale/ingest/coordinator.py`

**Bottleneck attuale**:
- Batch size piccoli (32 chunk default)
- GPU permetterebbe batch più grandi

**Impatto stimato**: 2-5x speedup aggiuntivo
- Aumentando batch size da 32 a 128-256 con GPU

**Modifiche necessarie**:
- Configurazione dinamica batch size basata su device
- Settings.py: aggiungere `embedding.batch_size_gpu`

### 1.4 Image Processing (PRIORITÀ BASSA)
**File**: `src/rag_gestionale/ingest/image_service.py`

**Bottleneck attuale**:
- PIL/Pillow usa CPU per resize/conversioni
- Impatto limitato (poche immagini per documento)

**Impatto stimato**: 2-3x speedup (marginal benefit)
- Richiederebbe librerie aggiuntive (torchvision, albumentations)

## 2. Librerie e Dipendenze

### 2.1 Librerie Già Presenti (pyproject.toml)
```toml
torch = ">=2.1.0"              # Supporta CUDA 11.8+ e 12.x
sentence-transformers = ">=2.2.0"  # Usa PyTorch backend
transformers = ">=4.36.0"      # Usa PyTorch backend
```

**Nessuna nuova libreria necessaria** - torch include già supporto CUDA.

### 2.2 Installazione CUDA Runtime
**Non gestita da Python** - richiede:
- NVIDIA GPU Driver
- CUDA Toolkit 11.8 o 12.x
- cuDNN (optional, già incluso in PyTorch binaries)

**Verifica installazione**:
```python
import torch
print(torch.cuda.is_available())  # True se CUDA disponibile
print(torch.cuda.get_device_name(0))  # Nome GPU
```

## 3. Modifiche al Codice

### 3.1 Configurazione Settings (✅ IMPLEMENTATO)
**File**: `src/rag_gestionale/config/settings.py`

**Modifiche applicate**:
```python
class Settings(BaseSettings):
    # Device configuration
    device_mode: str = Field(
        default="auto",
        description="Modalità device: 'auto' (usa GPU se disponibile), 'cuda' (forza GPU), 'cpu' (forza CPU)",
    )
    # ... resto configurazione

class EmbeddingSettings(BaseModel):
    model_name: str = "BAAI/bge-m3"
    batch_size: int = 32
    batch_size_gpu: int = 128  # ✅ NUOVO - batch più grandi su GPU

def get_device() -> str:
    """Determina il device da utilizzare basandosi sulla configurazione."""
    device_mode = settings.device_mode.lower()
    if device_mode == "cpu":
        return "cpu"
    elif device_mode == "cuda":
        return "cuda"  # Forza CUDA
    else:  # "auto"
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"
```

### 3.2 Variabile d'Ambiente (✅ IMPLEMENTATO)
**File**: `.env`

Per controllare la modalità CPU/GPU, impostare:
```bash
# Opzioni:
# - "auto" (default): usa GPU se disponibile, altrimenti CPU
# - "cuda": forza utilizzo GPU (errore se non disponibile)
# - "cpu": forza utilizzo CPU
RAG_DEVICE_MODE=auto

# Batch sizes configurabili
RAG_EMBEDDING__BATCH_SIZE=32        # CPU batch size
RAG_EMBEDDING__BATCH_SIZE_GPU=128   # GPU batch size
```

**Esempi d'uso**:
```bash
# Sviluppo locale senza GPU
RAG_DEVICE_MODE=cpu

# Produzione con GPU
RAG_DEVICE_MODE=auto

# Test specifici GPU (fail se non disponibile)
RAG_DEVICE_MODE=cuda
```

### 3.3 Batch Size Dinamico (✅ IMPLEMENTATO)
**File**: `src/rag_gestionale/retrieval/vector_store.py`

**Modifiche applicate** in `_generate_embeddings_batch()`:
```python
async def _generate_embeddings_batch(self, texts: List[str]) -> List:
    # Determina batch size in base al device
    device = self.embedding_model.device.type
    batch_size = (
        self.settings.embedding.batch_size_gpu
        if device == "cuda"
        else self.settings.embedding.batch_size
    )

    logger.debug(f"Batch size utilizzato: {batch_size} (device={device})")

    try:
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.embedding_model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=self.settings.embedding.normalize_embeddings,
                show_progress_bar=False,
            ),
        )
    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            logger.warning(f"CUDA OOM - riduco batch size da {batch_size} a {batch_size // 2}")
            # Retry con batch size ridotto
            embeddings = await loop.run_in_executor(
                None,
                lambda: self.embedding_model.encode(
                    texts,
                    batch_size=batch_size // 2,
                    normalize_embeddings=self.settings.embedding.normalize_embeddings,
                    show_progress_bar=False,
                ),
            )
        else:
            raise

    return embeddings
```

### 3.4 Vector Store Initialization (✅ IMPLEMENTATO)
**File**: `src/rag_gestionale/retrieval/vector_store.py`

**Modifiche applicate** in `initialize()`:
```python
async def initialize(self):
    # Determina device da utilizzare
    device = get_device()
    logger.info(
        f"Caricamento modello embedding: {self.settings.embedding.model_name} su device={device}"
    )

    self.embedding_model = SentenceTransformer(
        self.settings.embedding.model_name,
        device=device,  # ✅ Usa device configurato
    )

    logger.info(f"Vector store inizializzato (device={device})")
```

### 3.5 Reranker Initialization (✅ IMPLEMENTATO)
**File**: `src/rag_gestionale/retrieval/hybrid_retriever.py`

**Modifiche applicate** in `initialize()`:
```python
async def initialize(self):
    # Determina device da utilizzare
    device = get_device()
    logger.info(
        f"Caricamento reranker: {self.settings.retrieval.reranker_model} su device={device}"
    )

    # Carica reranker
    loop = asyncio.get_event_loop()
    self.reranker = await loop.run_in_executor(
        None,
        lambda: CrossEncoder(
            self.settings.retrieval.reranker_model,
            max_length=512,
            device=device,  # ✅ Usa device configurato
        ),
    )

    logger.info(f"Hybrid retriever inizializzato (device={device})")
```

## 4. Requisiti Hardware

### 4.1 GPU Minima
- **NVIDIA GPU** con compute capability 3.5+ (Maxwell o superiore)
- **VRAM**: 4GB minimum, 8GB+ raccomandato
- **CUDA**: 11.8 o 12.x

### 4.2 Memoria GPU Stimata
**BAAI/bge-m3** (embedding model):
- Modello: ~2.3GB VRAM
- Batch 32: +0.5GB
- Batch 128: +1.5GB
- **Totale**: ~4GB con batch 128

**BAAI/bge-reranker-large** (reranker):
- Modello: ~1.3GB VRAM
- Inference: +0.5GB
- **Totale**: ~2GB

**Simultaneo**: ~6GB VRAM (entrambi i modelli caricati)

### 4.3 GPU Raccomandate
- **Entry level**: RTX 3060 (12GB), RTX 4060 Ti (16GB)
- **Professional**: RTX 4070 (12GB), RTX 4080 (16GB)
- **Server**: A100 (40/80GB), H100 (80GB)

## 5. Performance Estimates

### 5.1 Ingest Pipeline
**Scenario**: 1000 documenti HTML (10,000 chunk totali)

| Fase | CPU (tempo) | GPU (tempo) | Speedup |
|------|-------------|-------------|---------|
| HTML parsing | 30s | 30s | 1x (no GPU benefit) |
| Embedding generation | 180s | 12s | **15x** |
| Vector store insert | 20s | 20s | 1x (I/O bound) |
| **TOTALE** | **230s** | **62s** | **3.7x** |

### 5.2 Query Pipeline
**Scenario**: Singola query con 50 risultati da reranking

| Fase | CPU (tempo) | GPU (tempo) | Speedup |
|------|-------------|-------------|---------|
| Query embedding | 80ms | 8ms | **10x** |
| Vector search | 50ms | 50ms | 1x (Qdrant server-side) |
| Lexical search | 30ms | 30ms | 1x (Tantivy CPU) |
| Reranking (50 docs) | 300ms | 25ms | **12x** |
| LLM generation | 2000ms | 2000ms | 1x (OpenAI API) |
| **TOTALE** | **2460ms** | **2113ms** | **1.16x** |

**Note**: Speedup query limitato perché dominated by LLM API call (2s). Beneficio maggiore su ingest e batch queries.

### 5.3 Batch Queries (es. evaluation)
**Scenario**: 100 query in batch

| Fase | CPU (tempo) | GPU (tempo) | Speedup |
|------|-------------|-------------|---------|
| 100 query embeddings | 8s | 0.8s | **10x** |
| 100 reranking ops | 30s | 2.5s | **12x** |
| Vector searches | 5s | 5s | 1x |
| **TOTALE (no LLM)** | **43s** | **8.3s** | **5.2x** |

## 6. Punti di Attenzione

### 6.1 Non Ottimizzabili con GPU
1. **LLM Generation**: OpenAI API (cloud-based)
2. **Lexical Search**: Tantivy (Rust, CPU-optimized)
3. **Qdrant Vector Search**: Server separato (già ottimizzato)
4. **HTML Parsing**: BeautifulSoup (CPU, I/O bound)
5. **Database I/O**: PostgreSQL queries

### 6.2 Trade-offs
- **Costo**: GPU dedicata vs tempo di processing
- **Deployment**: Complicazione per prod (driver, CUDA toolkit)
- **Compatibilità**: Solo NVIDIA (no AMD, no Mac M1/M2)
- **Energia**: GPU consuma 150-350W vs CPU 65-125W

### 6.3 Alternative a CUDA
- **CPU Optimization**: ONNX Runtime, OpenVINO (Intel)
- **Quantization**: INT8/FP16 models (2-4x speedup, no GPU)
- **Batch aggregation**: Accumulare query per batch processing
- **Model distillation**: Modelli più piccoli (es. bge-small invece di bge-m3)

## 7. Riepilogo Priorità

### ALTA PRIORITÀ (Quick Wins) ✅ COMPLETATE
1. ✅ **Embedding model GPU** - Implementato con device selection da env var
2. ✅ **Reranker GPU** - Implementato con device selection da env var
3. ✅ **Batch size dinamico** - Implementato con batch_size diverso per CPU/GPU
4. ✅ **Settings configuration** - Device selection via `RAG_DEVICE_MODE`
5. ✅ **CUDA OOM handling** - Retry automatico con batch size ridotto

### BASSA PRIORITÀ (Non implementate)
6. Image processing GPU (marginal benefit, richiede torchvision)
7. CUDA stream optimization (advanced, complesso, minimal benefit)

## 8. Stato Implementazione

### ✅ Fase 1 - COMPLETATA
- ✅ Modificato device in vector_store.py
- ✅ Modificato device in hybrid_retriever.py
- ✅ Aggiunta device config in settings.py
- ✅ Variabile d'ambiente `RAG_DEVICE_MODE`
- ✅ Logging device info all'inizializzazione

### ✅ Fase 2 - COMPLETATA
- ✅ Batch size dinamico (CPU: 32, GPU: 128)
- ✅ CUDA OOM error handling con retry automatico
- ✅ Logging batch size utilizzato

### Fase 3 (opzionale - NON implementata)
- ⏸️ Benchmark suite per confronto CPU vs GPU
- ⏸️ Mixed precision (FP16) per ulteriore speedup
- ⏸️ Memory profiling e ottimizzazione

## 9. Come Usare

### Verifica CUDA disponibile
```bash
python -c "import torch; print(f'CUDA disponibile: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

### Configurazione modalità
Modifica il file `.env`:
```bash
# Modalità automatica (raccomandato)
RAG_DEVICE_MODE=auto

# Forza CPU (sviluppo/debug)
RAG_DEVICE_MODE=cpu

# Forza GPU (produzione con GPU garantita)
RAG_DEVICE_MODE=cuda
```

### Verifica device utilizzato
Al avvio del sistema, controlla i log:
```
INFO | Caricamento modello embedding: BAAI/bge-m3 su device=cuda
INFO | Vector store inizializzato (device=cuda)
INFO | Caricamento reranker: BAAI/bge-reranker-large su device=cuda
INFO | Hybrid retriever inizializzato (device=cuda)
```

Durante l'elaborazione:
```
DEBUG | Batch size utilizzato: 128 (device=cuda)
```

---

## 10. Conclusione

**IMPLEMENTAZIONE COMPLETATA**: Con le modifiche implementate, il sistema ora supporta:
- ✅ **Switch automatico CPU/GPU** tramite variabile d'ambiente
- ✅ **Batch size ottimizzato** per ciascun device
- ✅ **Error handling CUDA OOM** con fallback automatico
- ✅ **Logging completo** per debugging

**Performance attese**:
- **Ingest**: 10-50x speedup (da ~3 min a ~30 sec per 1000 chunk)
- **Reranking**: 5-20x speedup (da ~300ms a ~25ms per 50 risultati)
- **Query singole**: 1.2x speedup (limitato da LLM API latency)
- **Batch queries**: 5x speedup (beneficio maggiore senza LLM)

**Requisiti hardware**:
- GPU NVIDIA con 6-8GB VRAM per operare con entrambi i modelli
- CUDA Toolkit 11.8+ installato
- Driver NVIDIA aggiornati
