# Correzioni Timeout e Problema 113 Immagini

## Data: 2025-10-18

---

## Problemi Risolti

### 1. ❌ Timeout in Streamlit durante Ingestione
**Problema**: L'app Streamlit mostrava "Errore" dopo ~5 minuti anche se l'ingest continuava nel backend.

**Soluzione**: ✅ Timeout aumentato da 300s (5min) a **1800s (30min)**

### 2. ❌ 113 Immagini in una Singola Fonte
**Problema**: Il parser HTML estraeva troppe immagini (icone, sprite, elementi UI)

**Soluzioni applicate**:
- ✅ Filtri per escludere icone e sprite (pattern `/icon`, `/sprite`, `/ui`, etc.)
- ✅ Dimensione minima aumentata da 50x50px a **100x100px**
- ✅ Controllo width/height HTML attributes
- ✅ **Estrazione immagini DISABILITATA temporaneamente** per concentrarsi sul testo

### 3. ❌ Contenuto Chunk Inadeguato
**Problema**: I chunk contenevano principalmente `[Figura: ...]` invece di testo utile.

**Soluzione**: ✅ Con immagini disabilitate, il parser si concentrerà solo sul testo

---

## File Modificati

1. **[streamlit_app.py](streamlit_app.py)**
   - Timeout ingestione: 300s → **1800s (30 minuti)**

2. **[html_parser.py](src/rag_gestionale/ingest/html_parser.py)**
   - Aggiunti filtri per escludere icone/sprite
   - Controllo dimensioni immagini migliorato

3. **[settings.py](src/rag_gestionale/config/settings.py)**
   - `image_storage.enabled`: `True` → **`False`** (temporaneo)
   - `image_storage.min_width`: `50` → **`100`** px
   - `image_storage.min_height`: `50` → **`100`** px

---

## Come Procedere

### Passo 1: Riavvia il Server FastAPI

**IMPORTANTE**: Devi riavviare il server per applicare le modifiche alle configurazioni!

```bash
# 1. Ferma il server FastAPI (CTRL+C)

# 2. Riavvia il server
python -m rag_gestionale.api.main
```

### Passo 2: Re-Ingest dalla App Streamlit

1. Apri l'app Streamlit
2. Vai al tab **"Ingestione"**
3. Inserisci l'URL:
   ```
   https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query
   ```
4. Clicca **"Avvia Ingestione"**
5. Attendi (ora non dovrebbe dare timeout)

### Passo 3: Verifica nei Log FastAPI

Durante l'ingestione, controlla il terminale FastAPI per vedere:

**Cosa cercare**:
```
✅ Pre-processing HTML: X -> Y chars (Z% riduzione)
✅ Estratte N sezioni da URL
✅ Documento grande/piccolo (X sezioni), uso streaming/standard
✅ Processing batch 1/X: sezioni 0-15
✅ ImageService NOT attivo (perché disabilitato)
```

**Cosa NON dovresti vedere**:
```
❌ "Scaricate 113 immagini" (troppo)
❌ Timeout errors
```

### Passo 4: Testa la Query

1. Vai al tab **"Ricerca"**
2. Inserisci la query:
   ```
   quali sono le visualizzazioni previste per il comando da editor query
   ```
3. Clicca **"Cerca"**

### Passo 5: Verifica il Risultato

**Cosa verificare**:
1. **Confidenza**: Dovrebbe essere > 0% (idealmente > 70%)
2. **Fonti**: Dovrebbero contenere TESTO reale, non solo `[Figura: ...]`
3. **Immagini**: Dovrebbero essere **0 immagini** per fonte (perché disabilitate)
4. **Risposta**: Dovrebbe contenere informazioni sulle visualizzazioni

### Esempio Output Atteso:

```
Confidenza: 85%
Risposta: Le visualizzazioni previste per il comando Editor Query includono...

FONTI:
  1. DesktopTeseo7 Comando Editor Query (Score: 0.82)
     URL: https://cassiopea.centrosistemi.it/zcswiki/.../Editor_Query
     Immagini: 0 (disabilitate)
     Contenuto: Le visualizzazioni disponibili sono:
     - Visualizzazione tabellare
     - Visualizzazione grafica
     - Visualizzazione personalizzata
     ...
```

---

## Debugging Aggiuntivo

### Se ancora non funziona:

#### 1. Verifica che l'URL sia stato re-ingerito
```bash
# Esegui lo script di verifica
uv run python scripts/test_query_simple.py
```

Dovresti vedere:
- Documenti indicizzati: > 110 (aumenta ad ogni re-ingest)
- URL atteso trovato nelle fonti: **SI**
- Contenuto: TESTO significativo (non solo `[Figura...]`)

#### 2. Controlla la dimensione HTML della pagina

```bash
# Se il problema persiste, la pagina potrebbe essere troppo grande
# o avere una struttura HTML complessa
```

Potresti provare a ridurre `RAG_INGEST__MAX_HTML_SIZE_CHARS` a `300000`:

```bash
# In .env
RAG_INGEST__MAX_HTML_SIZE_CHARS=300000
```

#### 3. Verifica il contenuto HTML grezzo

Visita la pagina nel browser:
```
https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query
```

Fai **CTRL+U** (View Source) e cerca la parola "visualizzazioni" nell'HTML.

Se NON la trovi, significa che il testo è generato da JavaScript e dovrai abilitare il browser headless (Playwright).

---

## Se Vuoi Riabilitare le Immagini (Dopo Test)

Una volta che il testo funziona correttamente, puoi riabilitare le immagini in modo controllato:

### In `.env` o settings.py:
```bash
# Riabilita immagini con filtri più stringenti
RAG_IMAGE_STORAGE__ENABLED=true
RAG_IMAGE_STORAGE__MIN_WIDTH=150
RAG_IMAGE_STORAGE__MIN_HEIGHT=150
```

Poi re-ingerisci di nuovo.

---

## Script di Test Disponibili

1. **`scripts/test_query_simple.py`** - Test query tramite API
2. **`scripts/reingest_url.py`** - Re-ingest URL specifico
3. **`scripts/check_indexed_url.py`** - Verifica chunk indicizzati

---

## Metriche di Successo

**Prima (PROBLEMA)**:
- ❌ Timeout dopo 5 min
- ❌ 113 immagini estratte
- ❌ Chunk con solo `[Figura: ...]`
- ❌ Confidenza 0%
- ❌ "Informazione non trovata"

**Dopo (ATTESO)**:
- ✅ Nessun timeout (30 min disponibili)
- ✅ 0 immagini (disabilitate temporaneamente)
- ✅ Chunk con TESTO reale
- ✅ Confidenza > 70%
- ✅ Risposta pertinente con visualizzazioni

---

## Contatti

Se dopo queste correzioni il problema persiste:

1. Controlla i log FastAPI durante l'ingestione
2. Esegui `scripts/test_query_simple.py` e condividi l'output
3. Verifica che l'HTML source contenga il testo "visualizzazioni"

---

**Modifiche implementate da**: Claude Code
**Data**: 2025-10-18
**Status**: ✅ Pronto per test
