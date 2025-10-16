# Quickstart: Ingestion Immagini - Fase 1

Guida rapida per testare la nuova funzionalità di ingestion immagini.

---

## Installazione Dipendenze

```bash
# Installa nuove dipendenze
uv pip install Pillow aiohttp

# Verifica installazione
python -c "from PIL import Image; import aiohttp; print('OK')"
```

---

## Configurazione

### 1. Variabili Ambiente (opzionale)

Aggiungi al file `.env`:

```bash
# Abilita estrazione immagini
RAG_IMAGE_STORAGE__ENABLED=true

# Percorso storage (default: ./storage/images)
RAG_IMAGE_STORAGE__STORAGE_BASE_PATH=./storage/images

# Filtri immagini
RAG_IMAGE_STORAGE__MIN_WIDTH=50
RAG_IMAGE_STORAGE__MIN_HEIGHT=50
RAG_IMAGE_STORAGE__MAX_FILE_SIZE_MB=10
```

**Nota:** Se non specificate, verranno usati i valori di default.

### 2. Crea Directory Storage

```bash
mkdir -p storage/images
```

---

## Test Rapido

### Test 1: Estrazione da PDF

Crea file di test `test_image_ingestion.py`:

```python
import asyncio
from pathlib import Path
from rag_gestionale.ingest.coordinator import IngestionCoordinator


async def test_pdf_ingestion():
    """Test estrazione immagini da PDF"""

    coordinator = IngestionCoordinator()

    # Inserisci qui il percorso del tuo PDF di test
    pdf_path = "test_data/manuale_esempio.pdf"

    if not Path(pdf_path).exists():
        print(f"ERRORE: File {pdf_path} non trovato")
        return

    print(f"Ingestione PDF: {pdf_path}")
    chunks = await coordinator._parse_pdf_file(pdf_path)

    print(f"\nRisultati:")
    print(f"  - Chunk estratti: {len(chunks)}")

    # Conta chunk con immagini
    chunks_with_images = [c for c in chunks if c.metadata.image_ids]
    print(f"  - Chunk con immagini: {len(chunks_with_images)}")

    # Dettagli immagini
    total_images = sum(len(c.metadata.image_ids) for c in chunks)
    print(f"  - Totale immagini estratte: {total_images}")

    # Mostra primi 3 chunk con immagini
    print("\nPrimi chunk con immagini:")
    for i, chunk in enumerate(chunks_with_images[:3], 1):
        print(f"\n{i}. Chunk ID: {chunk.metadata.id}")
        print(f"   Titolo: {chunk.metadata.title}")
        print(f"   Pagine: {chunk.metadata.page_range}")
        print(f"   Immagini: {len(chunk.metadata.image_ids)}")
        for img_id in chunk.metadata.image_ids:
            print(f"     - {img_id}")

    # Verifica file su disco
    storage_path = Path("./storage/images")
    if storage_path.exists():
        total_files = len(list(storage_path.rglob("*.png")))
        print(f"\nFile su disco: {total_files} immagini salvate")


if __name__ == "__main__":
    asyncio.run(test_pdf_ingestion())
```

**Esegui:**
```bash
python test_image_ingestion.py
```

**Output atteso:**
```
Ingestione PDF: test_data/manuale_esempio.pdf
Estratte 12 immagini da PDF test_data/manuale_esempio.pdf

Risultati:
  - Chunk estratti: 45
  - Chunk con immagini: 8
  - Totale immagini estratte: 12

Primi chunk con immagini:
1. Chunk ID: abc123#page1-2
   Titolo: Impostazioni IVA
   Pagine: [1, 2]
   Immagini: 2
     - abc123_p1_i0
     - abc123_p1_i1

File su disco: 12 immagini salvate
```

---

### Test 2: API Immagini

**1. Avvia server:**
```bash
python -m rag_gestionale.api.main
```

**2. Test endpoint statistiche:**
```bash
curl http://localhost:8000/images/storage/stats
```

**Response attesa:**
```json
{
  "total_images": 12,
  "total_size_bytes": 845632,
  "total_size_mb": 0.81,
  "total_sources": 1,
  "storage_path": "./storage/images"
}
```

**3. Test lista immagini:**

Prima ottieni il `source_hash` dai log o da un chunk:

```bash
# Esempio con source_hash = "a1b2c3d4e5f6"
curl http://localhost:8000/images/info/a1b2c3d4e5f6
```

**Response:**
```json
{
  "source_hash": "a1b2c3d4e5f6",
  "total": 12,
  "images": [
    {
      "filename": "page_1_img_0.png",
      "url": "/images/a1b2c3d4e5f6/page_1_img_0.png",
      "size_bytes": 45120,
      "format": "png"
    },
    ...
  ]
}
```

**4. Test scaricamento immagine:**
```bash
curl http://localhost:8000/images/a1b2c3d4e5f6/page_1_img_0.png --output test_image.png

# Verifica
file test_image.png
# Output: test_image.png: PNG image data, 800 x 600, 8-bit/color RGB
```

---

### Test 3: Ricerca con Immagini

**Ingesta documento e poi cerca:**

```bash
# 1. Ingesta
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "directory": "./test_data/manuali"
  }'

# 2. Cerca
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "parametro aliquota IVA",
    "top_k": 3
  }'
```

**Verifica che la response includa `images` nei `sources`:**

```json
{
  "query": "parametro aliquota IVA",
  "sources": [
    {
      "chunk": {
        "content": "...",
        "metadata": {
          "id": "...",
          "title": "Parametri IVA",
          "image_ids": ["abc123_p5_i0", "abc123_p5_i1"]
        }
      },
      "score": 0.87,
      "images": []  // Nota: per ora vuoto, arricchimento nella prossima PR
    }
  ]
}
```

---

## Verifica Implementazione

### Checklist Funzionalità

- [ ] **ImageService** istanziato correttamente
- [ ] **Immagini estratte** da PDF e salvate su disco
- [ ] **Chunk.metadata.image_ids** popolato
- [ ] **API /images** funzionante
- [ ] **Statistiche storage** corrette
- [ ] **Payload Qdrant** include `image_ids`

### Comandi Utili

```bash
# Verifica storage
ls -lh storage/images/*/

# Conta immagini
find storage/images -type f -name "*.png" | wc -l

# Dimensione storage
du -sh storage/images/

# Log estrazione
tail -f logs/rag.log | grep "immagini"
```

---

## Troubleshooting

### Problema: `ImportError: No module named 'PIL'`

**Soluzione:**
```bash
uv pip install Pillow
```

### Problema: `ImportError: No module named 'aiohttp'`

**Soluzione:**
```bash
uv pip install aiohttp
```

### Problema: Nessuna immagine estratta

**Debug:**
1. Verifica che il PDF contenga immagini:
   ```python
   import fitz
   doc = fitz.open("test.pdf")
   for page_num in range(doc.page_count):
       imgs = doc[page_num].get_images()
       print(f"Pagina {page_num + 1}: {len(imgs)} immagini")
   ```

2. Controlla log:
   ```bash
   tail -n 100 logs/rag.log | grep -i "error"
   ```

3. Verifica filtri dimensione:
   ```bash
   # Nel .env
   RAG_IMAGE_STORAGE__MIN_WIDTH=10
   RAG_IMAGE_STORAGE__MIN_HEIGHT=10
   ```

### Problema: API 404 per immagini

**Debug:**
1. Verifica che il file esista:
   ```bash
   ls storage/images/{source_hash}/
   ```

2. Verifica router registrato:
   ```python
   # In api/main.py
   app.include_router(images.router)
   ```

3. Controlla URL corretto:
   ```
   http://localhost:8000/images/{source_hash}/{filename}
   ```

---

## Prossimi Step

1. **Testa con manuali reali** del tuo gestionale
2. **Monitora storage** (crescita dimensioni)
3. **Valuta OCR** per screenshot UI (Fase 2)
4. **Feedback utenti** sull'utilità delle immagini

---

## Documentazione Completa

Per dettagli completi sull'implementazione, consulta:
- [Analisi iniziale](analisi_ingestion_immagini.md)
- [Implementazione Fase 1](implementazione_fase1_immagini.md)
- [API Reference](../src/rag_gestionale/api/routers/images.py)

---

**Buon testing!** 🚀
