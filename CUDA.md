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

### 3.1 Configurazione Settings
**File**: `src/rag_gestionale/config/settings.py`

**Aggiungere**:
```python
class EmbeddingSettings(BaseSettings):
    model_name: str = "BAAI/bge-m3"
    batch_size: int = 32
    batch_size_gpu: int = 128  # NUOVO - batch più grandi su GPU
    device: str = "auto"  # NUOVO - "auto", "cuda", "cpu"
```

### 3.2 Device Selection Logic
**Centralized device selection**:
```python
# Utility function da aggiungere
def get_device(device_setting: str) -> str:
    if device_setting == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device_setting
```

### 3.3 Batch Size Dinamico
**File**: `src/rag_gestionale/retrieval/vector_store.py`

**Modificare `_generate_embeddings_batch()`**:
```python
def _generate_embeddings_batch(self, texts: List[str]) -> np.ndarray:
    device = self.embedding_model.device.type
    batch_size = (
        self.settings.embedding.batch_size_gpu
        if device == "cuda"
        else self.settings.embedding.batch_size
    )

    # ... rest of method
```

### 3.4 Memory Management
**Aggiungere error handling per CUDA OOM**:
```python
try:
    embeddings = self.embedding_model.encode(
        batch,
        batch_size=batch_size,
        show_progress_bar=False
    )
except RuntimeError as e:
    if "out of memory" in str(e):
        logger.warning("CUDA OOM - fallback to CPU")
        # Fallback o batch più piccolo
    raise
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

### ALTA PRIORITÀ (Quick Wins)
1. ✅ **Embedding model GPU** - 1 riga di codice, 10-50x speedup ingest
2. ✅ **Reranker GPU** - 1 riga di codice, 5-20x speedup reranking

### MEDIA PRIORITÀ
3. **Batch size dinamico** - Sfruttare GPU memory per batch più grandi
4. **Settings configuration** - Device selection configurabile

### BASSA PRIORITÀ
5. Image processing GPU (marginal benefit)
6. CUDA stream optimization (advanced, complesso)

## 8. Implementazione Consigliata

**Fase 1** (1 ora dev):
- Modificare device in vector_store.py e hybrid_retriever.py
- Aggiungere device config in settings.py
- Test su macchina con GPU

**Fase 2** (2 ore dev):
- Batch size dinamico
- CUDA OOM error handling
- Logging device info (GPU name, VRAM usage)

**Fase 3** (opzionale):
- Benchmark suite per confronto CPU vs GPU
- Mixed precision (FP16) per ulteriore speedup
- Memory profiling e ottimizzazione

---

**CONCLUSIONE**: Con modifiche minime (2-3 righe di codice) si ottiene **10-50x speedup** su ingest e **5-12x** su reranking. Beneficio maggiore su batch processing, meno su singole query (dominated by LLM API latency).
