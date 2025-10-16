"""
Servizio per estrazione, salvataggio e gestione immagini dai documenti.
Supporta PDF e HTML con metadata tracking completo.
"""

import hashlib
import asyncio
from pathlib import Path
from typing import List, Optional, Dict
from io import BytesIO

import fitz  # PyMuPDF
from loguru import logger

try:
    from PIL import Image, ImageEnhance, ImageFilter

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import aiohttp

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import pytesseract

    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

from ..core.models import ImageMetadata, SourceFormat


class ImageService:
    """Servizio per estrazione, salvataggio e indicizzazione immagini"""

    def __init__(self, storage_base_path: str = "./storage/images", settings=None):
        self.storage_base_path = Path(storage_base_path)
        self.storage_base_path.mkdir(parents=True, exist_ok=True)

        # Importa settings se non passati
        if settings is None:
            from ..config.settings import get_settings

            settings = get_settings()

        self.settings = settings

        # Filtri per immagini valide
        self.min_width = settings.image_storage.min_width
        self.min_height = settings.image_storage.min_height
        self.max_file_size_mb = settings.image_storage.max_file_size_mb

        # OCR
        self.ocr_enabled = settings.image_storage.ocr_enabled and HAS_TESSERACT
        if settings.image_storage.ocr_enabled and not HAS_TESSERACT:
            logger.warning(
                "OCR abilitato ma pytesseract non disponibile. Installa pytesseract."
            )

        logger.info(
            f"ImageService inizializzato: storage={self.storage_base_path}, OCR={self.ocr_enabled}"
        )

    async def extract_and_save_pdf_images(
        self, doc: fitz.Document, source_url: str
    ) -> List[ImageMetadata]:
        """
        Estrae immagini da PDF e le salva su disco

        Args:
            doc: Documento PDF aperto con fitz
            source_url: URL sorgente del PDF

        Returns:
            Lista di ImageMetadata per immagini estratte
        """
        images_metadata = []
        source_hash = self._compute_url_hash(source_url)

        logger.info(f"Inizio estrazione immagini da PDF: {source_url}")

        try:
            for page_num in range(doc.page_count):
                page = doc[page_num]
                image_list = page.get_images()

                logger.debug(
                    f"Pagina {page_num + 1}: trovate {len(image_list)} immagini"
                )

                for img_index, img in enumerate(image_list):
                    try:
                        # Estrai immagine
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)

                        # Converti in RGB se necessario
                        if pix.n - pix.alpha >= 4:
                            # CMYK o altri formati, converti a RGB
                            pix = fitz.Pixmap(fitz.csRGB, pix)

                        # Valida dimensioni
                        if not self._is_valid_image(pix.width, pix.height):
                            logger.debug(
                                f"Immagine troppo piccola: {pix.width}x{pix.height}, skipping"
                            )
                            pix = None
                            continue

                        # Genera ID univoco
                        image_id = f"{source_hash}_p{page_num}_i{img_index}"

                        # Salva immagine
                        image_dir = self.storage_base_path / source_hash
                        image_dir.mkdir(exist_ok=True)
                        image_filename = f"page_{page_num + 1}_img_{img_index}.png"
                        image_path = image_dir / image_filename

                        # Salva come PNG
                        pix.save(str(image_path))

                        # Calcola hash contenuto
                        img_hash = self._compute_image_hash_from_pixmap(pix)

                        # Dimensione file
                        file_size = image_path.stat().st_size

                        # Verifica dimensione massima
                        if file_size > self.max_file_size_mb * 1024 * 1024:
                            logger.warning(
                                f"Immagine troppo grande ({file_size / 1024 / 1024:.2f}MB), skipping"
                            )
                            image_path.unlink()  # Elimina file
                            pix = None
                            continue

                        # OCR se abilitato
                        ocr_text = ""
                        if self.ocr_enabled:
                            ocr_text = await self.run_ocr(image_path)

                        # Crea metadata
                        img_meta = ImageMetadata(
                            id=image_id,
                            chunk_id="",  # Verrà assegnato durante chunking
                            source_url=source_url,
                            source_format=SourceFormat.PDF,
                            page_number=page_num + 1,
                            index_in_page=img_index,
                            storage_path=str(image_path),
                            image_url=f"/images/{source_hash}/{image_filename}",
                            width=pix.width,
                            height=pix.height,
                            format="png",
                            file_size_bytes=file_size,
                            caption=f"Immagine pagina {page_num + 1}",
                            ocr_text=ocr_text,
                            hash=img_hash,
                        )

                        images_metadata.append(img_meta)
                        logger.debug(f"Salvata immagine: {image_id}")

                        pix = None  # Libera memoria

                    except Exception as e:
                        logger.error(
                            f"Errore estrazione immagine pagina {page_num + 1}, index {img_index}: {e}"
                        )
                        continue

            logger.info(
                f"Estrazione completata: {len(images_metadata)} immagini salvate da PDF"
            )

        except Exception as e:
            logger.error(f"Errore durante estrazione immagini da PDF: {e}")

        return images_metadata

    async def download_and_save_html_images(
        self, figures: List[Dict[str, str]], source_url: str
    ) -> List[ImageMetadata]:
        """
        Scarica immagini da HTML e le salva

        Args:
            figures: Lista di dict con metadati figure (src, caption, alt)
            source_url: URL sorgente HTML

        Returns:
            Lista di ImageMetadata per immagini scaricate
        """
        if not HAS_AIOHTTP:
            logger.warning("aiohttp non disponibile, skip download immagini HTML")
            return []

        if not HAS_PIL:
            logger.warning("PIL non disponibile, skip download immagini HTML")
            return []

        images_metadata = []
        source_hash = self._compute_url_hash(source_url)

        logger.info(f"Inizio download immagini da HTML: {source_url}")

        # Crea session aiohttp
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for idx, figure in enumerate(figures):
                img_url = figure.get("src", "")
                if not img_url:
                    continue

                try:
                    # Scarica immagine
                    logger.debug(f"Download immagine {idx + 1}: {img_url}")
                    async with session.get(img_url) as resp:
                        if resp.status != 200:
                            logger.warning(
                                f"Errore download {img_url}: HTTP {resp.status}"
                            )
                            continue

                        img_data = await resp.read()

                        # Verifica dimensione
                        if len(img_data) > self.max_file_size_mb * 1024 * 1024:
                            logger.warning(
                                f"Immagine troppo grande ({len(img_data) / 1024 / 1024:.2f}MB), skipping"
                            )
                            continue

                        # Analizza immagine con PIL
                        try:
                            img = Image.open(BytesIO(img_data))
                            width, height = img.size
                            format_img = img.format or "png"

                            # Valida dimensioni
                            if not self._is_valid_image(width, height):
                                logger.debug(
                                    f"Immagine troppo piccola: {width}x{height}, skipping"
                                )
                                continue

                            # Salva immagine
                            image_dir = self.storage_base_path / source_hash
                            image_dir.mkdir(exist_ok=True)
                            image_filename = f"img_{idx}.{format_img.lower()}"
                            image_path = image_dir / image_filename

                            # Salva su disco
                            with open(image_path, "wb") as f:
                                f.write(img_data)

                            # Calcola hash
                            img_hash = self._compute_hash_from_bytes(img_data)

                            # Genera ID
                            image_id = f"{source_hash}_img_{idx}"

                            # OCR se abilitato
                            ocr_text = ""
                            if self.ocr_enabled:
                                ocr_text = await self.run_ocr(image_path)

                            # Crea metadata
                            img_meta = ImageMetadata(
                                id=image_id,
                                chunk_id="",
                                source_url=source_url,
                                source_format=SourceFormat.HTML,
                                page_number=None,
                                index_in_page=idx,
                                storage_path=str(image_path),
                                image_url=f"/images/{source_hash}/{image_filename}",
                                width=width,
                                height=height,
                                format=format_img.lower(),
                                file_size_bytes=len(img_data),
                                caption=figure.get("caption", figure.get("alt", "")),
                                ocr_text=ocr_text,
                                hash=img_hash,
                            )

                            images_metadata.append(img_meta)
                            logger.debug(f"Salvata immagine HTML: {image_id}")

                        except Exception as e:
                            logger.error(f"Errore apertura immagine con PIL: {e}")
                            continue

                except Exception as e:
                    logger.warning(f"Errore scaricamento immagine {img_url}: {e}")
                    continue

                # Piccolo delay per non sovraccaricare il server
                await asyncio.sleep(0.1)

        logger.info(
            f"Download completato: {len(images_metadata)} immagini salvate da HTML"
        )

        return images_metadata

    def get_images_by_chunk_id(
        self, chunk_id: str, all_images: List[ImageMetadata]
    ) -> List[ImageMetadata]:
        """
        Filtra immagini associate a uno specifico chunk

        Args:
            chunk_id: ID del chunk
            all_images: Lista completa immagini

        Returns:
            Lista di immagini associate al chunk
        """
        return [img for img in all_images if img.chunk_id == chunk_id]

    def _is_valid_image(self, width: int, height: int) -> bool:
        """Verifica se immagine ha dimensioni valide"""
        return width >= self.min_width and height >= self.min_height

    def _compute_url_hash(self, url: str) -> str:
        """Calcola hash breve dell'URL per organizzazione storage"""
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _compute_image_hash_from_pixmap(self, pix: fitz.Pixmap) -> str:
        """Calcola hash dell'immagine da Pixmap per deduplicazione"""
        # Usa primi 10KB del pixmap per hash veloce
        data = pix.tobytes()[:10240]
        return hashlib.sha1(data).hexdigest()

    def _compute_hash_from_bytes(self, data: bytes) -> str:
        """Calcola hash da bytes"""
        return hashlib.sha1(data).hexdigest()

    def _compute_file_hash(self, file_path: Path) -> str:
        """Calcola hash del file immagine"""
        with open(file_path, "rb") as f:
            data = f.read()
        return hashlib.sha1(data).hexdigest()

    async def cleanup_orphaned_images(self, valid_image_ids: List[str]) -> int:
        """
        Elimina immagini orfane (non più riferite da chunk)

        Args:
            valid_image_ids: Lista di ID immagini ancora valide

        Returns:
            Numero di immagini eliminate
        """
        deleted_count = 0

        try:
            # Scansiona directory storage
            for source_dir in self.storage_base_path.iterdir():
                if not source_dir.is_dir():
                    continue

                for img_file in source_dir.iterdir():
                    if not img_file.is_file():
                        continue

                    # Estrai ID dal percorso
                    # Formato: {source_hash}_p{page}_i{index}.png o {source_hash}_img_{index}.{ext}
                    img_id = self._extract_id_from_filename(
                        source_dir.name, img_file.name
                    )

                    if img_id and img_id not in valid_image_ids:
                        # Immagine orfana, elimina
                        img_file.unlink()
                        deleted_count += 1
                        logger.debug(f"Eliminata immagine orfana: {img_id}")

                # Elimina directory vuote
                if not any(source_dir.iterdir()):
                    source_dir.rmdir()
                    logger.debug(f"Eliminata directory vuota: {source_dir.name}")

        except Exception as e:
            logger.error(f"Errore durante cleanup immagini orfane: {e}")

        if deleted_count > 0:
            logger.info(
                f"Cleanup completato: eliminate {deleted_count} immagini orfane"
            )

        return deleted_count

    def _extract_id_from_filename(self, source_hash: str, filename: str) -> str:
        """Estrae ID immagine da filename"""
        # Rimuovi estensione
        name_no_ext = filename.rsplit(".", 1)[0]

        # Formato PDF: page_{num}_img_{index}
        if name_no_ext.startswith("page_"):
            parts = name_no_ext.split("_")
            if len(parts) >= 4:
                page_num = int(parts[1]) - 1  # Riporta a 0-indexed
                img_index = parts[3]
                return f"{source_hash}_p{page_num}_i{img_index}"

        # Formato HTML: img_{index}
        elif name_no_ext.startswith("img_"):
            img_index = name_no_ext.split("_")[1]
            return f"{source_hash}_img_{img_index}"

        return ""

    async def run_ocr(self, image_path: Path) -> str:
        """
        Esegue OCR su immagine usando Tesseract

        Args:
            image_path: Percorso immagine

        Returns:
            Testo estratto (stringa vuota se OCR fallisce)
        """
        if not self.ocr_enabled:
            return ""

        if not HAS_TESSERACT:
            logger.debug("Tesseract non disponibile, skip OCR")
            return ""

        if not HAS_PIL:
            logger.debug("PIL non disponibile, skip OCR")
            return ""

        try:
            # Carica immagine
            with Image.open(image_path) as img:
                # Pre-processing se abilitato
                if self.settings.image_storage.ocr_preprocessing:
                    img = self._preprocess_image_for_ocr(img)

                # Esegui OCR in thread pool per non bloccare async loop
                loop = asyncio.get_event_loop()
                text = await loop.run_in_executor(
                    None,
                    lambda: pytesseract.image_to_string(
                        img, lang=self.settings.image_storage.ocr_languages
                    ),
                )

                # Pulizia testo
                text = text.strip()

                # Filtra per confidenza se disponibile (richiede pytesseract con --oem 1)
                if text and len(text) > 5:  # Almeno 5 caratteri
                    logger.debug(
                        f"OCR estratto {len(text)} caratteri da {image_path.name}"
                    )
                    return text
                else:
                    logger.debug(
                        f"OCR nessun testo valido estratto da {image_path.name}"
                    )
                    return ""

        except Exception as e:
            logger.warning(f"Errore OCR su {image_path}: {e}")
            return ""

    def _preprocess_image_for_ocr(self, img: Image.Image) -> Image.Image:
        """
        Pre-processa immagine per migliorare OCR

        Tecniche:
        - Conversione grayscale
        - Aumento contrasto
        - Riduzione rumore
        - Upscaling per testo piccolo

        Args:
            img: Immagine PIL

        Returns:
            Immagine pre-processata
        """
        try:
            # Converti in RGB se necessario
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Upscaling se immagine piccola (testo piccolo)
            width, height = img.size
            if width < 800 or height < 600:
                # Raddoppia dimensioni
                new_size = (width * 2, height * 2)
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                logger.debug(f"Upscaling immagine: {width}x{height} → {new_size}")

            # Converti in grayscale
            img = img.convert("L")

            # Aumento contrasto
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)  # +50% contrasto

            # Aumento sharpness
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.3)

            # Riduzione rumore con filtro mediano
            img = img.filter(ImageFilter.MedianFilter(size=3))

            return img

        except Exception as e:
            logger.warning(f"Errore pre-processing immagine: {e}")
            return img  # Ritorna originale in caso di errore
