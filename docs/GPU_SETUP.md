# Configurazione GPU/CUDA per RAG System

## Introduzione

Il sistema RAG supporta l'accelerazione GPU tramite CUDA per migliorare significativamente le performance di embedding generation e reranking.

## Prerequisiti

### Hardware
- GPU NVIDIA con compute capability 3.5+ (Maxwell o superiore)
- Minimo 6-8GB VRAM (raccomandato)
- Esempi GPU supportate:
  - Entry level: RTX 3060 (12GB), RTX 4060 Ti (16GB)
  - Professional: RTX 4070 (12GB), RTX 4080 (16GB)
  - Server: A100, H100

### Software
1. **Driver NVIDIA** aggiornati
2. **CUDA Toolkit** 11.8 o 12.x
   - Download: https://developer.nvidia.com/cuda-downloads
3. **PyTorch con CUDA** (già incluso nelle dipendenze del progetto)

## Verifica Disponibilità CUDA

Prima di abilitare la GPU, verifica che CUDA sia disponibile:

```bash
python -c "import torch; print(f'CUDA disponibile: {torch.cuda.is_available()}'); print(f'GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"N/A\"}')"
```

Output atteso con GPU disponibile:
```
CUDA disponibile: True
GPU: NVIDIA GeForce RTX 4070
```

## Configurazione

### 1. File .env

Modifica il file `.env` nella root del progetto:

```bash
# Modalità device: "auto", "cuda", "cpu"
RAG_DEVICE_MODE=auto

# Batch sizes (opzionali, valori di default già ottimizzati)
RAG_EMBEDDING__BATCH_SIZE=32        # Batch size CPU
RAG_EMBEDDING__BATCH_SIZE_GPU=128   # Batch size GPU
```

### 2. Modalità Disponibili

| Modalità | Descrizione | Quando usare |
|----------|-------------|--------------|
| `auto` (default) | Usa GPU se disponibile, altrimenti CPU | **Raccomandato** per produzione |
| `cuda` | Forza utilizzo GPU (errore se non disponibile) | Test/debug GPU specifici |
| `cpu` | Forza utilizzo CPU | Sviluppo senza GPU, debug |

### 3. Esempi di Configurazione

**Sviluppo locale senza GPU:**
```bash
RAG_DEVICE_MODE=cpu
```

**Produzione con GPU disponibile:**
```bash
RAG_DEVICE_MODE=auto
```

**Server GPU dedicato (fail se GPU non disponibile):**
```bash
RAG_DEVICE_MODE=cuda
```

## Verifica Funzionamento

### 1. Log di Startup

All'avvio del sistema, controlla i log per confermare il device utilizzato:

```
INFO | Caricamento modello embedding: BAAI/bge-m3 su device=cuda
INFO | Vector store inizializzato (device=cuda)
INFO | Caricamento reranker: BAAI/bge-reranker-large su device=cuda
INFO | Hybrid retriever inizializzato (device=cuda)
```

### 2. Log durante Elaborazione

Durante l'ingest o le query, verifica il batch size utilizzato:

```
DEBUG | Batch size utilizzato: 128 (device=cuda)
```

Con CPU vedrai:
```
DEBUG | Batch size utilizzato: 32 (device=cpu)
```

## Performance Attese

### Con GPU (vs CPU)

| Operazione | Speedup | Tempo CPU | Tempo GPU |
|------------|---------|-----------|-----------|
| Ingest 1000 chunk | **15x** | ~180s | ~12s |
| Query embedding | **10x** | ~80ms | ~8ms |
| Reranking 50 docs | **12x** | ~300ms | ~25ms |
| Query completa | **1.2x** | ~2460ms | ~2113ms* |

*\*Speedup limitato su query singole perché dominated by LLM API call (2000ms)*

### Memoria GPU Utilizzata

| Componente | VRAM richiesta |
|------------|----------------|
| Embedding model (BAAI/bge-m3) | ~2.3GB |
| Batch processing (128) | ~1.5GB |
| Reranker (BAAI/bge-reranker-large) | ~1.3GB |
| **Totale simultaneo** | **~6GB** |

## Troubleshooting

### Errore: CUDA Out of Memory (OOM)

Il sistema gestisce automaticamente gli errori OOM riducendo il batch size:

```
WARNING | CUDA OOM - riduco batch size da 128 a 64
```

Se il problema persiste, riduci manualmente il batch size GPU nel `.env`:

```bash
RAG_EMBEDDING__BATCH_SIZE_GPU=64
```

### Errore: torch.cuda.is_available() ritorna False

**Possibili cause:**
1. Driver NVIDIA non installati/aggiornati
2. CUDA Toolkit non installato
3. PyTorch installato senza supporto CUDA

**Soluzione:**
```bash
# Verifica versione driver
nvidia-smi

# Reinstalla PyTorch con CUDA (se necessario)
uv pip uninstall torch
uv pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### Performance non migliorano con GPU

**Verifica:**
1. Controlla i log: stai effettivamente usando `device=cuda`?
2. Batch size GPU configurato? (default: 128)
3. Stai testando operazioni GPU-friendly? (ingest, batch queries)
   - Query singole hanno beneficio limitato (LLM API domina il tempo)

## Best Practices

### Sviluppo
- Usa `RAG_DEVICE_MODE=cpu` per sviluppo locale senza GPU
- Abilita `RAG_LOG_LEVEL=DEBUG` per vedere batch sizes e device info

### Staging/Test
- Usa `RAG_DEVICE_MODE=auto` per testare con/senza GPU
- Monitora log per confermare device detection

### Produzione
- Usa `RAG_DEVICE_MODE=auto` per flexibility
- Oppure `RAG_DEVICE_MODE=cuda` se GPU garantita (fail-fast)
- Monitora VRAM usage con `nvidia-smi`
- Considera Mixed Precision (FP16) per GPU più veloci (implementazione futura)

## Riferimenti

- Analisi completa: [CUDA.md](../CUDA.md)
- Configurazione settings: [src/rag_gestionale/config/settings.py](../src/rag_gestionale/config/settings.py)
- PyTorch CUDA docs: https://pytorch.org/docs/stable/cuda.html
- NVIDIA CUDA: https://developer.nvidia.com/cuda-zone
