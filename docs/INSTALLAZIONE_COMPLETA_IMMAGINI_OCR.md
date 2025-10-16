# Guida Installazione Completa: Immagini + OCR

**Sistema:** RAG-Manualistica v2.0.0
**Feature:** Ingestion Immagini con OCR
**Piattaforme:** Windows, Linux, macOS

---

## Prerequisiti

- Python 3.11 o 3.12
- uv (package manager)
- Accesso a filesystem per storage immagini
- (Opzionale) Tesseract OCR per estrazione testo

---

## Installazione Step-by-Step

### Step 1: Dipendenze Python

```bash
# Installa le nuove dipendenze
uv pip install Pillow aiohttp pytesseract

# Verifica installazione
python -c "from PIL import Image; import aiohttp; print('✅ Pillow e aiohttp OK')"
python -c "import pytesseract; print('✅ pytesseract OK')"
```

**Se errori:**
```bash
# Reinstalla da zero
uv pip uninstall Pillow aiohttp pytesseract
uv pip install --force-reinstall Pillow aiohttp pytesseract
```

---

### Step 2: Tesseract OCR (Binario)

#### Windows

**Opzione A: Installer (Consigliato)**
```powershell
# 1. Scarica installer da:
https://github.com/UB-Mannheim/tesseract/wiki

# 2. Esegui installer
#    - Seleziona "Additional language data"
#    - Spunta: Italian, English
#    - Path default: C:\Program Files\Tesseract-OCR

# 3. Aggiungi a PATH
$env:Path += ";C:\Program Files\Tesseract-OCR"
[Environment]::SetEnvironmentVariable("Path", $env:Path, "Machine")

# 4. Verifica
tesseract --version
tesseract --list-langs
# Dovrebbe mostrare: ita, eng
```

**Opzione B: Chocolatey**
```powershell
choco install tesseract

# Installa language packs
choco install tesseract-language-pack-ita
choco install tesseract-language-pack-eng

tesseract --version
```

**Troubleshooting Windows:**
```python
# Se tesseract non in PATH, specifica percorso in codice:
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

#### Linux (Debian/Ubuntu)

```bash
# Installa Tesseract + language packs
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-ita tesseract-ocr-eng

# Verifica
tesseract --version
tesseract --list-langs

# Dovrebbe mostrare:
# List of available languages (3):
# eng
# ita
# osd
```

**Altre distro:**
```bash
# Fedora
sudo dnf install tesseract tesseract-langpack-ita tesseract-langpack-eng

# Arch
sudo pacman -S tesseract tesseract-data-ita tesseract-data-eng

# openSUSE
sudo zypper install tesseract-ocr tesseract-ocr-traineddata-italian tesseract-ocr-traineddata-english
```

#### macOS

```bash
# Homebrew
brew install tesseract tesseract-lang

# Verifica
tesseract --version
tesseract --list-langs
```

**Troubleshooting macOS:**
```bash
# Se manca lingua italiana
brew reinstall tesseract-lang

# Path language data (se problemi)
export TESSDATA_PREFIX=/opt/homebrew/share/tessdata
```

---

### Step 3: Configurazione

#### Crea/Modifica File `.env`

```bash
# Nella root del progetto
nano .env
```

**Aggiungi:**
```bash
# ============================================
# CONFIGURAZIONE IMMAGINI + OCR
# ============================================

# Storage Immagini
RAG_IMAGE_STORAGE__ENABLED=true
RAG_IMAGE_STORAGE__STORAGE_BASE_PATH=./storage/images
RAG_IMAGE_STORAGE__MIN_WIDTH=50
RAG_IMAGE_STORAGE__MIN_HEIGHT=50
RAG_IMAGE_STORAGE__MAX_FILE_SIZE_MB=10

# OCR
RAG_IMAGE_STORAGE__OCR_ENABLED=true
RAG_IMAGE_STORAGE__OCR_LANGUAGES=ita+eng
RAG_IMAGE_STORAGE__OCR_MIN_CONFIDENCE=30
RAG_IMAGE_STORAGE__OCR_PREPROCESSING=true
RAG_IMAGE_STORAGE__OCR_TIMEOUT_SECONDS=30
```

#### Crea Directory Storage

```bash
# Linux/macOS
mkdir -p storage/images

# Windows PowerShell
New-Item -ItemType Directory -Force -Path storage\images
```

---

### Step 4: Verifica Installazione

#### Test 1: Import Moduli

```python
# test_imports.py
from rag_gestionale.ingest.image_service import ImageService
from rag_gestionale.config.settings import get_settings

settings = get_settings()
print(f"Storage Path: {settings.image_storage.storage_base_path}")
print(f"OCR Enabled: {settings.image_storage.ocr_enabled}")
print(f"OCR Languages: {settings.image_storage.ocr_languages}")

service = ImageService()
print(f"ImageService OCR: {service.ocr_enabled}")

if service.ocr_enabled:
    print("✅ Installazione completa SUCCESSO")
else:
    print("⚠️  OCR disabilitato (Tesseract non trovato?)")
```

```bash
python test_imports.py
```

**Output Atteso:**
```
Storage Path: ./storage/images
OCR Enabled: True
OCR Languages: ita+eng
ImageService OCR: True
✅ Installazione completa SUCCESSO
```

#### Test 2: OCR su Immagine Test

```python
# test_ocr.py
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from rag_gestionale.ingest.image_service import ImageService

async def test_ocr():
    # Crea immagine test con testo
    img = Image.new('RGB', (400, 100), color='white')
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()

    d.text((10, 10), "Test OCR: Aliquota IVA 22%", fill='black', font=font)

    # Salva
    test_path = Path("test_ocr_image.png")
    img.save(test_path)
    print(f"Immagine test creata: {test_path}")

    # OCR
    service = ImageService()
    text = await service.run_ocr(test_path)

    print(f"\n{'='*50}")
    print(f"Testo estratto ({len(text)} caratteri):")
    print(f"{'='*50}")
    print(text)
    print(f"{'='*50}")

    # Cleanup
    test_path.unlink()

    # Verifica
    if "OCR" in text and "IVA" in text:
        print("\n✅ OCR funziona correttamente!")
        return True
    else:
        print("\n⚠️  OCR estratto testo ma qualità bassa")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_ocr())
    exit(0 if result else 1)
```

```bash
python test_ocr.py
```

**Output Atteso:**
```
Immagine test creata: test_ocr_image.png

==================================================
Testo estratto (27 caratteri):
==================================================
Test OCR: Aliquota IVA 22%
==================================================

✅ OCR funziona correttamente!
```

#### Test 3: Ingestion Completa

```python
# test_ingestion_full.py
import asyncio
from rag_gestionale.ingest.coordinator import IngestionCoordinator

async def test():
    coordinator = IngestionCoordinator()

    # Verifica inizializzazione
    print(f"ImageService: {'✅ Attivo' if coordinator.image_service else '❌ Disabilitato'}")
    if coordinator.image_service:
        print(f"OCR: {'✅ Attivo' if coordinator.image_service.ocr_enabled else '❌ Disabilitato'}")

    # Test con file dummy (opzionale)
    # chunks = await coordinator.ingest_from_directory("./test_data")
    # print(f"Chunk estratti: {len(chunks)}")

    print("\n✅ Sistema pronto per ingestion!")

asyncio.run(test())
```

```bash
python test_ingestion_full.py
```

---

## Troubleshooting

### Problema: `TesseractNotFoundError`

**Sintomo:**
```
pytesseract.pytesseract.TesseractNotFoundError: tesseract is not installed or it's not in your PATH
```

**Soluzioni:**

1. **Verifica installazione:**
   ```bash
   tesseract --version
   ```

2. **Aggiungi a PATH (Windows):**
   ```powershell
   $env:Path += ";C:\Program Files\Tesseract-OCR"
   [Environment]::SetEnvironmentVariable("Path", $env:Path, "User")
   ```

3. **Specifica percorso manualmente:**
   ```python
   # In src/rag_gestionale/ingest/image_service.py
   # Aggiungi dopo import pytesseract:
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

---

### Problema: `Language 'ita' not found`

**Sintomo:**
```
Error opening data file \Tesseract-OCR\tessdata/ita.traineddata
```

**Soluzioni:**

1. **Reinstalla con language packs:**
   ```bash
   # Windows
   # Usa installer e seleziona "Italian" in "Additional language data"

   # Linux
   sudo apt-get install tesseract-ocr-ita

   # macOS
   brew reinstall tesseract-lang
   ```

2. **Download manuale:**
   ```bash
   # Scarica da:
   https://github.com/tesseract-ocr/tessdata/raw/main/ita.traineddata

   # Copia in tessdata folder:
   # Windows: C:\Program Files\Tesseract-OCR\tessdata\
   # Linux: /usr/share/tesseract-ocr/4.00/tessdata/
   # macOS: /opt/homebrew/share/tessdata/
   ```

3. **Usa solo inglese (temporaneo):**
   ```bash
   # In .env
   RAG_IMAGE_STORAGE__OCR_LANGUAGES=eng
   ```

---

### Problema: OCR restituisce testo vuoto

**Debug:**

1. **Verifica immagine manualmente:**
   ```bash
   tesseract test.png stdout -l ita+eng
   ```

2. **Testa preprocessing:**
   ```python
   from rag_gestionale.ingest.image_service import ImageService
   from PIL import Image

   service = ImageService()
   img = Image.open("test.png")
   preprocessed = service._preprocess_image_for_ocr(img)
   preprocessed.show()  # Visivamente meglio?
   ```

3. **Disabilita preprocessing:**
   ```bash
   # In .env
   RAG_IMAGE_STORAGE__OCR_PREPROCESSING=false
   ```

4. **Aumenta timeout:**
   ```bash
   RAG_IMAGE_STORAGE__OCR_TIMEOUT_SECONDS=60
   ```

---

### Problema: `ImportError: cannot import name 'ImageEnhance'`

**Soluzione:**
```bash
# Reinstalla Pillow
uv pip uninstall Pillow
uv pip install --force-reinstall Pillow
```

---

### Problema: Directory `storage/images` permission denied

**Linux/macOS:**
```bash
sudo chown -R $USER:$USER storage/
chmod -R 755 storage/
```

**Windows:**
```powershell
icacls storage /grant Everyone:(OI)(CI)F /T
```

---

## Configurazioni Avanzate

### Ottimizzazione per Screenshot UI

```bash
# .env - Configurazione ottimale per screenshot
RAG_IMAGE_STORAGE__MIN_WIDTH=100
RAG_IMAGE_STORAGE__MIN_HEIGHT=100
RAG_IMAGE_STORAGE__OCR_PREPROCESSING=true
RAG_IMAGE_STORAGE__OCR_LANGUAGES=ita+eng
```

### Ottimizzazione per Scansioni Documenti

```bash
# .env - Configurazione ottimale per scansioni
RAG_IMAGE_STORAGE__MIN_WIDTH=200
RAG_IMAGE_STORAGE__MIN_HEIGHT=200
RAG_IMAGE_STORAGE__OCR_MIN_CONFIDENCE=40
RAG_IMAGE_STORAGE__OCR_PREPROCESSING=true
```

### Disabilita OCR (Solo Immagini)

```bash
# .env - Se Tesseract non disponibile
RAG_IMAGE_STORAGE__ENABLED=true
RAG_IMAGE_STORAGE__OCR_ENABLED=false
```

---

## Verifica Finale

### Checklist Pre-Produzione

- [ ] Python 3.11/3.12 installato
- [ ] `uv pip install Pillow aiohttp pytesseract` completato
- [ ] Tesseract OCR installato e in PATH
- [ ] Language packs `ita` e `eng` disponibili
- [ ] File `.env` configurato
- [ ] Directory `storage/images` creata
- [ ] Test import moduli: OK
- [ ] Test OCR su immagine test: OK
- [ ] Test ingestion: OK
- [ ] API avviabile senza errori

### Comando Test Finale

```bash
# Test completo
python -c "
import asyncio
from PIL import Image, ImageDraw
from pathlib import Path
from rag_gestionale.ingest.image_service import ImageService

async def test():
    # Crea immagine
    img = Image.new('RGB', (300, 80), 'white')
    d = ImageDraw.Draw(img)
    d.text((10,10), 'Test Installazione OK', fill='black')
    img.save('test.png')

    # OCR
    service = ImageService()
    text = await service.run_ocr(Path('test.png'))

    # Cleanup
    Path('test.png').unlink()

    # Verifica
    assert service.ocr_enabled, 'OCR non abilitato'
    assert 'Test' in text or 'OK' in text, 'OCR fallito'
    print('✅ INSTALLAZIONE COMPLETA E FUNZIONANTE')

asyncio.run(test())
"
```

**Se OK:**
```
✅ INSTALLAZIONE COMPLETA E FUNZIONANTE
```

---

## Post-Installazione

### Prima Ingestion

```bash
# Crea directory test
mkdir -p test_data/manuali

# Copia alcuni PDF/HTML di test in test_data/manuali/

# Avvia API
python -m rag_gestionale.api.main

# In altro terminale, ingesta
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"directory": "./test_data/manuali"}'

# Verifica immagini estratte
curl http://localhost:8000/images/storage/stats | jq

# Cerca
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "parametro IVA", "top_k": 5}' | jq
```

### Monitoring

```bash
# Log OCR
tail -f logs/rag.log | grep -i "ocr"

# Dimensione storage
du -sh storage/images/

# Conta immagini
find storage/images -type f | wc -l
```

---

## Support & Docs

- **Documentazione completa:** [docs/](.)
- **Guida rapida:** [QUICKSTART_IMMAGINI.md](QUICKSTART_IMMAGINI.md)
- **Troubleshooting:** [implementazione_fase2_ocr.md#troubleshooting](implementazione_fase2_ocr.md#troubleshooting)
- **API Reference:** [api/routers/images.py](../src/rag_gestionale/api/routers/images.py)

---

**Installazione completata! Il sistema è pronto per processare manuali con estrazione immagini e OCR.**
