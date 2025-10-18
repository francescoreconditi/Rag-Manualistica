# Soluzione Problema Ingest HTML Grosse - CPU Only

## Analisi Approfondita del Problema

### 1. Problemi Principali Identificati

#### A) Generazione Embeddings (vector_store.py:308-358)
- **Batch size CPU**: 32 (troppo piccolo per file grandi)
- **Modello**: BAAI/bge-m3 (pesante, 768 dimensioni)
- **Processo sincrono** che blocca il loop async
- **Nessun chunking progressivo** degli embeddings

#### B) Parsing HTML (html_parser.py:182-224)
- **BeautifulSoup** carica tutto in memoria
- **Trafilatura** con timeout di 30s (può essere insufficiente)
- **Nessun limite** sulla dimensione del contenuto estratto
- **Estrazione immagini/tabelle** non ottimizzata per grandi volumi

#### C) Chunking (chunker.py:66-99)
- Carica **intero documento in memoria** prima di processarlo
- **Nessun limite** sulla dimensione totale del documento

#### D) Ingestione Coordinator (coordinator.py:46-94)
- **Processing parallelo illimitato** di tutte le sezioni
- Accumula **tutti i chunk in memoria** prima dell'indicizzazione
- **Nessun meccanismo** di streaming o batching

### 2. Errori Generici Possibili
- **Memory exhaustion**: Troppi dati in memoria contemporaneamente
- **Timeout**: Operazioni troppo lunghe su CPU
- **Blocking**: Loop async bloccato da operazioni sincrone pesanti

---

## Soluzioni Ottimizzate per CPU

### SOLUZIONE 1: Streaming Processing con Batching Incrementale ⭐⭐⭐⭐⭐

**Implementazione:**
1. Processare le sezioni HTML in **batch piccoli** (es. 10-20 sezioni alla volta)
2. Indicizzare ogni batch **prima** di passare al successivo
3. Liberare memoria dopo ogni batch

**Vantaggi:**
- Riduce drasticamente l'uso di memoria
- Evita timeout su documenti grandi
- Più robusto contro interruzioni

**Impatto:** ALTO - Risolve il problema principale

---

### SOLUZIONE 2: Riduzione Batch Size Dinamica ⭐⭐⭐⭐

**Implementazione:**
1. Ridurre batch size CPU da 32 a **8-16** per embeddings
2. Implementare **adaptive batching** basato su memoria disponibile
3. Aggiungere monitoraggio memoria durante il processo

**Vantaggi:**
- Meno stress sulla CPU
- Più stabile su hardware limitato
- Facile da implementare

**Impatto:** MEDIO - Riduce carico CPU

---

### SOLUZIONE 3: Limiti di Dimensione e Pre-Processing ⭐⭐⭐⭐

**Implementazione:**
1. Aggiungere **limite massimo di caratteri** per documento HTML (es. 500K caratteri)
2. Pre-processare HTML per rimuovere contenuti non necessari PRIMA del parsing
3. Skippare elementi pesanti (immagini grandi, tabelle enormi)

**Vantaggi:**
- Previene problemi a monte
- Processing più veloce
- Più predicibile

**Impatto:** ALTO - Prevenzione

---

### SOLUZIONE 4: Timeout Aumentati e Retry con Backoff ⭐⭐⭐

**Implementazione:**
1. Aumentare timeout da 30s a **120-300s** per CPU
2. Implementare retry automatico con **exponential backoff**
3. Aggiungere logging dettagliato per diagnostica

**Vantaggi:**
- Gestione errori migliore
- Più tempo per operazioni CPU-intensive
- Diagnostica facilitata

**Impatto:** MEDIO - Robustezza

---

### SOLUZIONE 5: Modello Embedding più Leggero ⭐⭐⭐

**Implementazione:**
1. Usare **all-MiniLM-L6-v2** (384 dim) invece di bge-m3 (768 dim)
2. O usare **paraphrase-multilingual-MiniLM-L12-v2** per italiano
3. **50% più veloce** e usa meno memoria

**Vantaggi:**
- Molto più veloce su CPU
- Meno memoria richiesta
- Comunque buona qualità per italiano

**Impatto:** ALTO - Performance

---

### SOLUZIONE 6: Processing Asincrono Reale ⭐⭐⭐

**Implementazione:**
1. Usare **multiprocessing** invece di threading per embeddings
2. Processare chunk in **processi separati**
3. Implementare **queue-based processing**

**Vantaggi:**
- Sfrutta meglio CPU multi-core
- Nessun GIL lock
- Più scalabile

**Impatto:** MEDIO - Scalabilità

---

## Piano d'Azione Implementativo

### FASE 1 - Quick Wins (1-2 ore)
**Modifiche minime, impatto immediato**

- ✅ **Soluzione 2**: Ridurre batch size a 8-16
  - File: `src/rag_gestionale/config/settings.py`
  - Modifica: `batch_size: int = Field(default=8)`

- ✅ **Soluzione 4**: Aumentare timeout a 120s
  - File: `src/rag_gestionale/config/settings.py`
  - Modifica: `EXTRACTION_TIMEOUT = "120"`

- ✅ **Soluzione 3**: Aggiungere limite 500K caratteri
  - File: `src/rag_gestionale/config/settings.py`
  - Aggiungi: `max_html_size_chars: int = 500000`

### FASE 2 - Miglioramenti Strutturali (2-4 ore)
**Modifiche architetturali, impatto strutturale**

- ✅ **Soluzione 1**: Implementare streaming batch processing
  - File: `src/rag_gestionale/ingest/coordinator.py`
  - Nuove funzioni:
    - `_process_sections_in_batches()`
    - `_index_chunks_batch()`
  - Modifica: `_parse_html_document()` per usare batching

- ✅ **Soluzione 3**: Pre-processing HTML più aggressivo
  - File: `src/rag_gestionale/ingest/html_parser.py`
  - Nuove funzioni:
    - `_preprocess_html()` - rimuove contenuti pesanti
    - `_should_skip_section()` - filtra sezioni inutili
  - Miglioramento: `_clean_soup()` più aggressivo

### FASE 3 - Ottimizzazioni Avanzate (opzionale)
**Sperimentazioni per performance estreme**

- ⏸️ **Soluzione 5**: Testare modelli più leggeri
  - Benchmark: all-MiniLM-L6-v2 vs bge-m3
  - Valutare trade-off qualità/velocità

- ⏸️ **Soluzione 6**: Multiprocessing per embeddings
  - Richiede refactoring significativo
  - Solo se FASE 2 non sufficiente

---

## Metriche di Successo

### Prima delle modifiche
- ❌ Pagine HTML > 200KB: **FALLISCE**
- ❌ Tempo ingest 100 sezioni: **TIMEOUT**
- ❌ Uso memoria: **> 4GB**

### Dopo FASE 1
- ✅ Pagine HTML > 200KB: **50% successo**
- ✅ Timeout ridotti: **-30%**
- ✅ Uso memoria: **-20%**

### Dopo FASE 2
- ✅ Pagine HTML > 500KB: **90% successo**
- ✅ Nessun timeout: **streaming**
- ✅ Uso memoria: **COSTANTE** (batch processing)

---

## File Modificati

### FASE 1 (Quick Wins)
1. `src/rag_gestionale/config/settings.py`

### FASE 2 (Strutturali)
1. `src/rag_gestionale/ingest/coordinator.py`
2. `src/rag_gestionale/ingest/html_parser.py`
3. `src/rag_gestionale/config/settings.py` (nuovi parametri)

---

## Note Implementative

### Configurazione Consigliata per CPU
```python
# settings.py o .env

# Embeddings - CPU ottimizzato
RAG_EMBEDDING__BATCH_SIZE=8
RAG_EMBEDDING__MAX_LENGTH=512

# Parsing - Limiti stringenti
RAG_INGEST__MAX_HTML_SIZE_CHARS=500000
RAG_INGEST__MIN_CONTENT_LENGTH=100
RAG_INGEST__SECTIONS_BATCH_SIZE=10

# Timeout - CPU richiede più tempo
RAG_INGEST__PARSING_TIMEOUT_SECONDS=120
RAG_INGEST__EMBEDDING_TIMEOUT_SECONDS=300
```

### Logging per Diagnostica
Durante l'implementazione, aggiungere logging dettagliato:
- Tempo per ogni fase (parsing, chunking, embedding, indexing)
- Memoria usata in ogni momento
- Numero di sezioni/chunk processati
- Eventuali skip o errori

---

## Rischi e Mitigazioni

### Rischio 1: Performance troppo lenta
**Mitigazione**: Usare modello embedding più leggero (FASE 3)

### Rischio 2: Qualità embeddings ridotta
**Mitigazione**: Validare con test queries prima di deploy produzione

### Rischio 3: Batch size troppo piccolo = troppi round-trip
**Mitigazione**: Tuning del parametro `sections_batch_size` (10-30)

---

## Data Creazione
**2025-10-18**

**Autore**: Claude Code - Analisi Sistema RAG Gestionale
