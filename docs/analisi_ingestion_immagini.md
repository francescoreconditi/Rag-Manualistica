# Analisi: Ingestion Immagini nel Sistema RAG

**Data:** 2025-10-16
**Scopo:** Valutare la difficoltà di implementare l'ingestion delle immagini dai manuali tecnici per mostrare le immagini "vicino" alle risposte del sistema RAG.

---

## 1. Executive Summary

**Difficoltà complessiva: MEDIA-ALTA (7/10)**

Il progetto ha già una **base solida** per gestire le immagini:
- ✅ Estrazione immagini da PDF già implementata (metodo `extract_images_with_ocr`)
- ✅ Estrazione figure da HTML già implementata (metodo `_extract_figure`)
- ✅ Struttura dati `figures` nelle sezioni PDF/HTML
- ✅ Metadati ricchi per tracciamento sorgenti

Tuttavia, le immagini **non vengono ancora indicizzate nel vector store** e mancano:
- ❌ Salvataggio fisico delle immagini estratte
- ❌ Generazione di embeddings multimodali (CLIP, LLaVA, etc.)
- ❌ Indicizzazione immagini nel database vettoriale
- ❌ Sistema di retrieval per immagini
- ❌ API per servire le immagini agli utenti

---

## 2. Stato Attuale dell'Ingestion Immagini

### 2.1 Cosa Funziona Già

#### A. Estrazione Immagini da PDF (pdf_parser.py:403-432)

Il metodo `extract_images_with_ocr()` estrae già immagini da PyMuPDF:

```python
def extract_images_with_ocr(self, doc: fitz.Document, page_num: int) -> List[Dict[str, str]]:
    images = []
    page = doc[page_num]
    image_list = page.get_images()

    for img_index, img in enumerate(image_list):
        xref = img[0]
        pix = fitz.Pixmap(doc, xref)

        if pix.n - pix.alpha < 4:  # Solo RGB/Gray
            img_data = {
                "page": page_num + 1,
                "index": img_index,
                "width": pix.width,
                "height": pix.height,
                "caption": f"Immagine {img_index + 1} - Pagina {page_num + 1}",
                "ocr_text": "",  # Placeholder per OCR futuro
            }
            images.append(img_data)

        pix = None
    return images
```

**Problemi:**
1. Le immagini vengono estratte ma **i dati binari (Pixmap) non vengono salvati**
2. Il metodo viene definito ma **non viene chiamato** nel flusso di ingestion
3. Non c'è salvataggio su disco o storage

#### B. Estrazione Figure da HTML (html_parser.py:442-473)

Il metodo `_extract_figure()` estrae già metadati delle figure HTML:

```python
def _extract_figure(self, figure_element: Tag, base_url: str) -> Optional[Dict[str, str]]:
    result = {"src": "", "alt": "", "caption": "", "type": "image"}

    # Trova img
    img = figure_element.find("img") if figure_element.name != "img" else figure_element

    if img:
        src = img.get("src", "")
        if src:
            result["src"] = urljoin(base_url, src) if not src.startswith("http") else src
        result["alt"] = img.get("alt", "")

    # Trova caption
    caption_element = figure_element.find(["figcaption", "caption"])
    if caption_element:
        result["caption"] = clean_html_tags(caption_element.get_text()).strip()

    return result if result["src"] or result["caption"] else None
```

**Cosa viene salvato:**
- `src`: URL dell'immagine (assoluto)
- `alt`: Testo alternativo
- `caption`: Didascalia
- `type`: "image"

**Problemi:**
1. Le immagini **non vengono scaricate** (solo URL salvato)
2. Nessuna indicizzazione nel vector store
3. Metodo chiamato in `_extract_sections()` ma `figures` salvate solo nella sezione, non indicizzate separatamente

#### C. Struttura Dati Sezioni

Entrambe le classi `PDFSection` e `HTMLSection` hanno:

```python
self.figures: List[Dict[str, str]] = []
```

Questo array raccoglie le figure estratte ma:
- **Non viene propagato ai chunk** durante il chunking
- **Non viene salvato nei metadati** dei chunk (ChunkMetadata non ha campo `figures`)
- **Non viene indicizzato** nel vector store

---

## 3. Architettura Proposta per Ingestion Immagini

### 3.1 Approcci Possibili

#### Approccio A: **Embeddings Multimodali (CLIP/LLaVA)** - CONSIGLIATO

**Modelli disponibili:**
- **CLIP** (OpenAI): Allinea immagini e testo in spazio vettoriale comune
- **LLaVA** (Microsoft): Large Language and Vision Assistant
- **BLIP-2**: Bootstrapping Language-Image Pre-training

**Vantaggi:**
- ✅ Ricerca semantica testo → immagine
- ✅ Query tipo "mostra la schermata del parametro IVA"
- ✅ Embeddings compatibili con il vector store esistente (Qdrant)
- ✅ Nessun cambio di architettura database

**Svantaggi:**
- ⚠️ Richiede modelli pesanti (1-5 GB)
- ⚠️ Maggiore tempo di ingestion
- ⚠️ GPU consigliata per performance

#### Approccio B: **Metadata-only Indexing** - PIÙ SEMPLICE

**Strategia:**
- Salvare immagini con metadati testuali ricchi (caption, alt, OCR)
- Indicizzare solo il testo estratto (caption + OCR)
- Associare immagini ai chunk tramite `chunk_id`

**Vantaggi:**
- ✅ Più semplice da implementare
- ✅ Riutilizza embeddings testuali esistenti (BAAI/bge-m3)
- ✅ Nessun modello aggiuntivo
- ✅ Più veloce

**Svantaggi:**
- ⚠️ Ricerca limitata alla qualità delle caption
- ⚠️ Non supporta ricerca visuale semantica
- ⚠️ Dipende da OCR per immagini di screenshot UI

---

## 4. Implementazione Consigliata: Approccio B (Metadata-only)

### 4.1 Componenti da Implementare

#### A. Storage Fisico delle Immagini

**Opzione 1: Filesystem Locale**
```
/storage/
  /images/
    /{source_hash}/
      /page_1_img_0.png
      /page_1_img_1.png
      ...
```

**Opzione 2: Object Storage (AWS S3, MinIO)**
- Migliore per produzione
- Scalabilità
- CDN per servire immagini

**Consiglio:** Iniziare con filesystem locale, poi migrare a S3/MinIO.

#### B. Nuovo Modello Dati: `ImageMetadata`

Aggiungere a `core/models.py`:

```python
class ImageMetadata(BaseModel):
    """Metadati per immagini estratte"""

    # Identificazione
    id: str = Field(..., description="ID univoco immagine (hash)")
    chunk_id: str = Field(..., description="ID del chunk a cui appartiene")

    # Posizione nel documento
    source_url: str = Field(..., description="URL del documento sorgente")
    source_format: SourceFormat = Field(..., description="PDF o HTML")
    page_number: Optional[int] = Field(None, description="Numero pagina (per PDF)")
    index_in_page: int = Field(0, description="Indice nell'array immagini pagina")

    # Storage
    storage_path: str = Field(..., description="Percorso file immagine salvato")
    image_url: str = Field(..., description="URL pubblico per servire immagine")

    # Proprietà immagine
    width: int
    height: int
    format: str = Field(default="png", description="Formato (png, jpg, etc.)")
    file_size_bytes: int

    # Contenuto testuale
    caption: str = Field(default="", description="Didascalia/alt text")
    ocr_text: str = Field(default="", description="Testo estratto con OCR")

    # Posizione spaziale (per PDF)
    bbox: Optional[Tuple[float, float, float, float]] = Field(None, description="Bounding box")

    # Metadati aggiuntivi
    hash: str = Field(..., description="Hash contenuto immagine (dedup)")
    created_at: datetime = Field(default_factory=datetime.now)
```

#### C. Modifica a `ChunkMetadata`

Aggiungere campo per immagini associate:

```python
class ChunkMetadata(BaseModel):
    # ... campi esistenti ...

    # Immagini associate
    image_ids: List[str] = Field(default_factory=list, description="ID immagini in questo chunk")
```

#### D. Service per Gestione Immagini

Nuovo file: `src/rag_gestionale/ingest/image_service.py`

```python
class ImageService:
    """Servizio per estrazione, salvataggio e indicizzazione immagini"""

    def __init__(self, storage_base_path: str):
        self.storage_base_path = Path(storage_base_path)
        self.storage_base_path.mkdir(parents=True, exist_ok=True)

    async def extract_and_save_pdf_images(
        self,
        doc: fitz.Document,
        source_url: str
    ) -> List[ImageMetadata]:
        """Estrae immagini da PDF e le salva su disco"""
        images_metadata = []
        source_hash = hashlib.md5(source_url.encode()).hexdigest()[:8]

        for page_num in range(doc.page_count):
            page = doc[page_num]
            image_list = page.get_images()

            for img_index, img in enumerate(image_list):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)

                if pix.n - pix.alpha < 4:  # RGB/Gray
                    # Genera ID univoco
                    image_id = f"{source_hash}_p{page_num}_i{img_index}"

                    # Salva immagine
                    image_dir = self.storage_base_path / source_hash
                    image_dir.mkdir(exist_ok=True)
                    image_path = image_dir / f"page_{page_num}_img_{img_index}.png"
                    pix.save(str(image_path))

                    # OCR (opzionale)
                    ocr_text = await self._run_ocr(image_path)

                    # Crea metadata
                    img_meta = ImageMetadata(
                        id=image_id,
                        chunk_id="",  # Verrà assegnato durante chunking
                        source_url=source_url,
                        source_format=SourceFormat.PDF,
                        page_number=page_num + 1,
                        index_in_page=img_index,
                        storage_path=str(image_path),
                        image_url=f"/images/{source_hash}/page_{page_num}_img_{img_index}.png",
                        width=pix.width,
                        height=pix.height,
                        format="png",
                        file_size_bytes=image_path.stat().st_size,
                        caption=f"Immagine pagina {page_num + 1}",
                        ocr_text=ocr_text,
                        hash=self._compute_image_hash(pix),
                    )
                    images_metadata.append(img_meta)

                pix = None  # Libera memoria

        return images_metadata

    async def download_and_save_html_images(
        self,
        figures: List[Dict[str, str]],
        source_url: str
    ) -> List[ImageMetadata]:
        """Scarica immagini da HTML e le salva"""
        images_metadata = []
        source_hash = hashlib.md5(source_url.encode()).hexdigest()[:8]

        async with aiohttp.ClientSession() as session:
            for idx, figure in enumerate(figures):
                img_url = figure.get("src")
                if not img_url:
                    continue

                try:
                    # Scarica immagine
                    async with session.get(img_url) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()

                            # Salva
                            image_dir = self.storage_base_path / source_hash
                            image_dir.mkdir(exist_ok=True)
                            image_path = image_dir / f"img_{idx}.png"

                            with open(image_path, "wb") as f:
                                f.write(img_data)

                            # Analizza immagine
                            with Image.open(image_path) as img:
                                width, height = img.size
                                format_img = img.format

                            # OCR
                            ocr_text = await self._run_ocr(image_path)

                            # Metadata
                            image_id = f"{source_hash}_img_{idx}"
                            img_meta = ImageMetadata(
                                id=image_id,
                                chunk_id="",
                                source_url=source_url,
                                source_format=SourceFormat.HTML,
                                page_number=None,
                                index_in_page=idx,
                                storage_path=str(image_path),
                                image_url=f"/images/{source_hash}/img_{idx}.png",
                                width=width,
                                height=height,
                                format=format_img.lower(),
                                file_size_bytes=image_path.stat().st_size,
                                caption=figure.get("caption", ""),
                                ocr_text=ocr_text,
                                hash=self._compute_file_hash(image_path),
                            )
                            images_metadata.append(img_meta)

                except Exception as e:
                    logger.warning(f"Errore scaricamento immagine {img_url}: {e}")

        return images_metadata

    async def _run_ocr(self, image_path: Path) -> str:
        """Esegue OCR su immagine usando Tesseract"""
        try:
            import pytesseract
            from PIL import Image

            with Image.open(image_path) as img:
                text = pytesseract.image_to_string(img, lang='ita+eng')
            return text.strip()
        except Exception as e:
            logger.warning(f"OCR fallito per {image_path}: {e}")
            return ""

    def _compute_image_hash(self, pix: fitz.Pixmap) -> str:
        """Calcola hash dell'immagine per deduplicazione"""
        import hashlib
        # Usa i primi 1000 byte del pixmap
        data = pix.tobytes()[:1000]
        return hashlib.sha1(data).hexdigest()

    def _compute_file_hash(self, file_path: Path) -> str:
        """Calcola hash del file immagine"""
        import hashlib
        with open(file_path, "rb") as f:
            data = f.read()
        return hashlib.sha1(data).hexdigest()
```

#### E. Integrazione con Chunker

Modificare `src/rag_gestionale/ingest/chunker.py`:

```python
class IntelligentChunker:
    def __init__(self, image_service: Optional[ImageService] = None):
        # ... esistente ...
        self.image_service = image_service

    async def chunk_document(
        self,
        sections: List[Union[PDFSection, HTMLSection]],
        metadata: Dict,
        images_metadata: List[ImageMetadata] = None
    ) -> List[DocumentChunk]:
        """Chunking con associazione immagini"""

        chunks = []

        for section in sections:
            # ... chunking esistente ...

            # Associa immagini al chunk
            if images_metadata and hasattr(section, 'figures'):
                # Trova immagini che appartengono a questa sezione
                section_images = self._match_images_to_section(
                    section,
                    images_metadata
                )

                # Aggiungi image_ids ai metadata del chunk
                chunk.metadata.image_ids = [img.id for img in section_images]

                # Arricchisci contenuto chunk con testo OCR
                if section_images:
                    ocr_texts = [img.ocr_text for img in section_images if img.ocr_text]
                    if ocr_texts:
                        chunk.content += "\n\n[Testo dalle immagini]\n" + "\n".join(ocr_texts)

        return chunks

    def _match_images_to_section(
        self,
        section: Union[PDFSection, HTMLSection],
        images_metadata: List[ImageMetadata]
    ) -> List[ImageMetadata]:
        """Associa immagini a sezione in base a pagina/posizione"""

        matched = []

        if isinstance(section, PDFSection):
            # Match per range pagine
            for img in images_metadata:
                if img.page_number and section.page_start <= img.page_number <= section.page_end:
                    matched.append(img)

        elif isinstance(section, HTMLSection):
            # Match per ordine sequenziale (semplificato)
            # In HTML le figure sono già associate nella sezione
            matched = images_metadata[:len(section.figures)]

        return matched
```

#### F. Vector Store per Immagini

Due opzioni:

**Opzione 1: Collection separata in Qdrant**

```python
# In vector_store.py
await self.async_client.create_collection(
    collection_name="gestionale_images",
    vectors_config=VectorParams(
        size=384,  # Dimensione embedding testuale (caption + OCR)
        distance=Distance.COSINE,
    ),
)

# Indicizza immagini con embeddings del testo (caption + OCR)
async def add_images(self, images: List[ImageMetadata]):
    for img in images:
        # Combina caption e OCR
        text = f"{img.caption}\n{img.ocr_text}"
        embedding = await self._generate_embedding(text)

        payload = {
            "image_id": img.id,
            "chunk_id": img.chunk_id,
            "source_url": img.source_url,
            "caption": img.caption,
            "ocr_text": img.ocr_text,
            "image_url": img.image_url,
            "storage_path": img.storage_path,
            "width": img.width,
            "height": img.height,
        }

        await self.async_client.upsert(
            collection_name="gestionale_images",
            points=[PointStruct(
                id=hash(img.id),
                vector=embedding.tolist(),
                payload=payload,
            )]
        )
```

**Opzione 2: Payload esteso nella collection principale**

Salvare i metadati immagini direttamente nel payload dei chunk:

```python
# In _chunk_to_payload
payload["images"] = [
    {
        "id": img_id,
        "url": img.image_url,
        "caption": img.caption,
    }
    for img_id in chunk.metadata.image_ids
]
```

**Consiglio:** Usare **Opzione 2** (payload esteso) per semplicità iniziale.

#### G. API Endpoint per Servire Immagini

Nuovo router: `src/rag_gestionale/api/routers/images.py`

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(prefix="/images", tags=["images"])

STORAGE_BASE = Path("./storage/images")

@router.get("/{source_hash}/{filename}")
async def get_image(source_hash: str, filename: str):
    """Serve immagine dal filesystem"""
    image_path = STORAGE_BASE / source_hash / filename

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Immagine non trovata")

    return FileResponse(image_path)


@router.get("/by-chunk/{chunk_id}")
async def get_images_by_chunk(chunk_id: str):
    """Ritorna tutte le immagini associate a un chunk"""
    # Query vector store per recuperare chunk
    chunk = await vector_store.get_chunk_by_id(chunk_id)

    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk non trovato")

    # Ritorna URL immagini
    images = []
    for img_id in chunk.metadata.image_ids:
        # Recupera metadata immagine (da DB o cache)
        img_meta = await get_image_metadata(img_id)
        images.append({
            "id": img_meta.id,
            "url": img_meta.image_url,
            "caption": img_meta.caption,
            "width": img_meta.width,
            "height": img_meta.height,
        })

    return {"chunk_id": chunk_id, "images": images}
```

#### H. Modifica alla RAGResponse

Aggiungere immagini alla risposta:

```python
class SearchResult(BaseModel):
    chunk: DocumentChunk
    score: float
    explanation: Optional[str] = None
    images: List[Dict[str, str]] = Field(default_factory=list)  # NUOVO

class RAGResponse(BaseModel):
    # ... esistente ...
    sources: List[SearchResult]
    all_images: List[Dict[str, str]] = Field(default_factory=list)  # NUOVO
```

Nel retriever, popolare `images` per ogni `SearchResult`:

```python
async def retrieve(self, query: str) -> List[SearchResult]:
    results = await self.hybrid_retriever.search(query)

    # Arricchisci con immagini
    for result in results:
        if result.chunk.metadata.image_ids:
            result.images = await self._fetch_images(result.chunk.metadata.image_ids)

    return results
```

---

## 5. Stima Effort di Implementazione

### 5.1 Breakdown Task

| Task | Complessità | Ore stimate |
|------|-------------|-------------|
| 1. Creazione `ImageMetadata` e aggiornamento `ChunkMetadata` | Bassa | 2h |
| 2. Implementazione `ImageService` (estrazione + salvataggio PDF) | Media | 8h |
| 3. Implementazione download immagini HTML | Media | 4h |
| 4. Integrazione OCR (Tesseract) | Bassa | 3h |
| 5. Modifica `PDFParser` per chiamare `ImageService` | Bassa | 2h |
| 6. Modifica `HTMLParser` per chiamare `ImageService` | Bassa | 2h |
| 7. Modifica `IntelligentChunker` per associare immagini | Media | 6h |
| 8. Estensione payload Qdrant per immagini | Bassa | 2h |
| 9. API endpoint `/images` per servire file | Bassa | 3h |
| 10. API endpoint `/images/by-chunk` | Bassa | 2h |
| 11. Modifica `RAGResponse` e retriever | Media | 4h |
| 12. Testing end-to-end | Alta | 8h |
| 13. Documentazione | Bassa | 3h |
| **TOTALE** | | **~49 ore** |

### 5.2 Dipendenze Esterne da Aggiungere

```toml
# In pyproject.toml
dependencies = [
    # ... esistenti ...

    # Per OCR
    "pytesseract>=0.3.10",

    # Per manipolazione immagini
    "Pillow>=10.0.0",

    # Per download async immagini HTML
    "aiohttp>=3.9.0",

    # Per storage S3 (opzionale, fase 2)
    # "boto3>=1.28.0",
    # "minio>=7.2.0",
]
```

**Tesseract OCR:**
- Richiede installazione sistema operativo
- Windows: Scaricare installer da https://github.com/UB-Mannheim/tesseract/wiki
- Linux: `apt-get install tesseract-ocr tesseract-ocr-ita`
- Modello lingua italiana necessario

---

## 6. Roadmap Consigliata

### Fase 1: MVP (Minimum Viable Product) - 2 settimane

**Obiettivo:** Mostrare immagini associate alle risposte RAG

**Deliverables:**
1. ✅ Estrazione e salvataggio immagini da PDF/HTML
2. ✅ Associazione immagini ai chunk tramite `image_ids`
3. ✅ API `/images` per servire file
4. ✅ Modifica `RAGResponse` per includere immagini
5. ✅ Testing su 1-2 manuali campione

**Limitazioni accettabili:**
- Nessun OCR (solo caption)
- Storage filesystem locale (non S3)
- Nessuna ricerca immagini (solo associazione)

### Fase 2: OCR e Ricerca Testuale - 1 settimana

**Obiettivo:** Migliorare qualità ricerca includendo testo OCR

**Deliverables:**
1. ✅ Integrazione Tesseract OCR
2. ✅ Arricchimento chunk con testo OCR
3. ✅ Query tipo "mostra schermata parametro IVA" funzionante

### Fase 3: Embeddings Multimodali (Opzionale) - 2-3 settimane

**Obiettivo:** Ricerca semantica visuale

**Deliverables:**
1. ✅ Integrazione modello CLIP
2. ✅ Collection Qdrant separata per immagini
3. ✅ Endpoint ricerca `/search/images`
4. ✅ Hybrid retrieval testo + immagini

### Fase 4: Produzione - 1 settimana

**Obiettivo:** Scalabilità e robustezza

**Deliverables:**
1. ✅ Migrazione storage S3/MinIO
2. ✅ CDN per servire immagini
3. ✅ Compression/resize automatici
4. ✅ Caching (Redis)
5. ✅ Monitoring e logging

---

## 7. Rischi e Mitigazioni

### Rischio 1: Storage Crescita Incontrollata

**Descrizione:** I manuali PDF possono contenere centinaia di immagini, molte delle quali irrilevanti (loghi, decorazioni).

**Mitigazione:**
- Filtrare immagini piccole (< 100x100px)
- Deduplicazione tramite hash
- Compressione automatica (PNG → JPG per screenshot)
- Limiti dimensione (es. max 5MB per immagine)

### Rischio 2: OCR Qualità Scadente

**Descrizione:** Screenshot UI hanno testo piccolo, OCR può fallire.

**Mitigazione:**
- Pre-processing immagini (upscaling, contrasto)
- Usare modelli OCR migliori (EasyOCR, PaddleOCR)
- Fallback a caption se OCR vuoto
- Mantenere comunque l'immagine anche se OCR fallisce

### Rischio 3: Latenza Ingestion

**Descrizione:** Scaricare immagini HTML + OCR può rallentare molto l'ingestion.

**Mitigazione:**
- Download parallelo con `asyncio.gather()`
- OCR asincrono con worker pool
- Skip OCR per immagini grandi (> 2MB)
- Progress bar per utente

### Rischio 4: Costi Storage

**Descrizione:** S3 storage può diventare costoso con migliaia di immagini.

**Mitigazione:**
- Usare S3 Intelligent-Tiering
- Lifecycle policy per archiviazione vecchie versioni
- Valutare MinIO self-hosted come alternativa
- Compression aggressiva

---

## 8. Esempi di User Experience

### Prima (Senza Immagini)

**Query Utente:** "Come si imposta il parametro aliquota IVA?"

**Risposta RAG:**
```
Per impostare l'aliquota IVA, vai in Menu > Contabilità > Impostazioni IVA.
Inserisci il valore nel campo "Aliquota %" e salva.

Fonti:
- Manuale Contabilità v2.1, Sezione "Parametri IVA"
```

### Dopo (Con Immagini)

**Query Utente:** "Come si imposta il parametro aliquota IVA?"

**Risposta RAG:**
```
Per impostare l'aliquota IVA, vai in Menu > Contabilità > Impostazioni IVA.
Inserisci il valore nel campo "Aliquota %" e salva.

Fonti:
- Manuale Contabilità v2.1, Sezione "Parametri IVA"

Immagini rilevanti:
┌─────────────────────────────┐
│ [Screenshot UI]             │
│ Schermata Impostazioni IVA  │
│ Contabilità > Parametri     │
└─────────────────────────────┘

┌─────────────────────────────┐
│ [Diagramma]                 │
│ Flusso configurazione IVA   │
└─────────────────────────────┘
```

**Valore aggiunto:**
- ✅ Utente vede esattamente dove cliccare
- ✅ Riduce ambiguità nelle istruzioni
- ✅ Miglior esperienza utente complessiva

---

## 9. Alternative Considerate

### Alternativa 1: Nessuna Ingestion, Solo Link

**Descrizione:** Non salvare immagini, solo linkare al PDF/HTML originale.

**Pro:**
- Zero effort implementativo
- Nessun storage aggiuntivo

**Contro:**
- ❌ Utente deve aprire PDF e cercare pagina
- ❌ Nessuna ricerca per immagini
- ❌ Esperienza utente scadente

**Verdetto:** ❌ Non consigliato

### Alternativa 2: Screenshot Rendering Runtime

**Descrizione:** Renderizzare PDF/HTML al volo per mostrare screenshot.

**Pro:**
- Immagini sempre aggiornate
- Nessun storage

**Contro:**
- ❌ Latenza elevata (rendering lento)
- ❌ Richiede headless browser
- ❌ Difficile highlightare porzioni specifiche

**Verdetto:** ❌ Non consigliato per fase iniziale

### Alternativa 3: Solo Immagini Annotate Manualmente

**Descrizione:** Permettere caricamento manuale immagini da admin.

**Pro:**
- Qualità garantita
- Controllo totale

**Contro:**
- ❌ Effort manuale enorme
- ❌ Non scala con centinaia di manuali

**Verdetto:** ⚠️ Utile come integrazione, non come soluzione principale

---

## 10. Conclusioni e Raccomandazioni

### Verdetto Finale

**L'implementazione dell'ingestion immagini è FATTIBILE e CONSIGLIATA.**

**Priorità: ALTA**
- Valore utente molto elevato
- Architettura già parzialmente pronta
- Effort gestibile (7-10 giorni per MVP)

### Raccomandazioni

1. **Partire con Fase 1 (MVP senza OCR)**
   - Implementare storage filesystem locale
   - Associare immagini ai chunk tramite metadati
   - Testare su 2-3 manuali pilota

2. **Aggiungere OCR in Fase 2**
   - Valutare qualità OCR su screenshot reali
   - Se qualità bassa, considerare EasyOCR/PaddleOCR

3. **Rimandare embeddings multimodali (CLIP) a Fase 3**
   - Richiede GPU per performance accettabili
   - Benefit marginale rispetto a OCR + caption
   - Valutare dopo aver visto adoption utenti

4. **Pianificare migrazione S3 fin da subito**
   - Usare abstraction layer (ImageStorage interface)
   - Implementare prima filesystem, poi S3
   - Evitare lock-in su storage locale

### Next Steps Immediati

1. ✅ Creare branch `feature/image-ingestion`
2. ✅ Implementare `ImageMetadata` model
3. ✅ Implementare `ImageService` con estrazione PDF
4. ✅ Test su 1 manuale PDF campione
5. ✅ Review architettura con team
6. ✅ Proseguire con implementazione completa

---

## 11. Appendice: Codice di Esempio Completo

### A. Flusso Ingestion Completo con Immagini

```python
# In coordinator.py

async def ingest_pdf_with_images(self, pdf_path: str):
    """Ingestion PDF con estrazione immagini"""

    # 1. Parse PDF (esistente)
    parser = PDFParser()
    sections, metadata = parser.parse_from_path(pdf_path)

    # 2. Estrai e salva immagini (NUOVO)
    image_service = ImageService(storage_base_path="./storage/images")
    doc = fitz.open(pdf_path)
    images_metadata = await image_service.extract_and_save_pdf_images(
        doc,
        metadata["source_url"]
    )
    doc.close()

    # 3. Chunking con associazione immagini (MODIFICATO)
    chunker = IntelligentChunker(image_service=image_service)
    chunks = await chunker.chunk_document(
        sections,
        metadata,
        images_metadata=images_metadata
    )

    # 4. Indicizzazione (esistente + payload esteso)
    await self.vector_store.add_chunks(chunks)
    await self.lexical_search.add_chunks(chunks)

    logger.info(f"Ingestione completata: {len(chunks)} chunk, {len(images_metadata)} immagini")
```

### B. Query con Immagini nella Risposta

```python
# In hybrid_retriever.py

async def retrieve_with_images(self, query: str) -> RAGResponse:
    """Retrieval con immagini associate"""

    # 1. Ricerca standard
    results = await self.search(query, top_k=10)

    # 2. Arricchisci con immagini
    all_images = []
    for result in results:
        if result.chunk.metadata.image_ids:
            # Recupera metadati immagini dal payload
            images_data = []
            for img_id in result.chunk.metadata.image_ids:
                # Immagini già nel payload chunk
                img_info = {
                    "id": img_id,
                    "url": f"/images/{img_id}",
                    "caption": "...",  # Dal payload
                }
                images_data.append(img_info)
                all_images.append(img_info)

            result.images = images_data

    # 3. Genera risposta
    response = RAGResponse(
        query=query,
        query_type=self.classify_query(query),
        answer=await self.generate_answer(query, results),
        sources=results,
        all_images=all_images,  # Tutte le immagini rilevanti
        confidence=0.85,
        processing_time_ms=123,
    )

    return response
```

---

**Fine Analisi**

Per domande o chiarimenti, contattare il team di sviluppo.
