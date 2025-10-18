"""
Coordinatore del sistema di ingestione.
Orchestrazione di crawling, parsing e preprocessing per scalabilità massiva.
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

from ..core.models import (
    DocumentChunk,
    ChunkMetadata,
    ContentType,
    SourceFormat,
    ImageMetadata,
)
from ..core.utils import compute_content_hash, extract_breadcrumbs
from ..config.settings import get_settings
from .crawler import WebCrawler, CrawlResult
from .html_parser import HTMLParser, HTMLSection
from .pdf_parser import PDFParser, PDFSection
from .image_service import ImageService


class IngestionCoordinator:
    """Coordinatore principale per l'ingestione di documenti"""

    def __init__(self):
        self.settings = get_settings()
        self.html_parser = HTMLParser()
        self.pdf_parser = PDFParser()
        self.processed_hashes: set = set()

        # ImageService per estrazione immagini
        if self.settings.image_storage.enabled:
            self.image_service = ImageService(
                storage_base_path=self.settings.image_storage.storage_base_path
            )
        else:
            self.image_service = None

    async def ingest_from_urls(self, urls: List[str]) -> List[DocumentChunk]:
        """
        Ingestione completa da lista di URL

        Args:
            urls: Lista di URL da processare

        Returns:
            Lista di chunk processati
        """
        logger.info(f"Avvio ingestione di {len(urls)} URL")

        all_chunks = []

        # Step 1: Crawling
        async with WebCrawler() as crawler:
            crawl_results = await crawler.crawl_urls(urls)

        logger.info(f"Crawling completato: {len(crawl_results)} documenti")

        # Step 2: Parsing parallelo
        parse_tasks = []
        for result in crawl_results:
            if result.is_html:
                task = self._parse_html_document(result)
            elif result.is_pdf:
                task = self._parse_pdf_document(result)
            else:
                continue  # Skip unsupported formats

            parse_tasks.append(task)

        if parse_tasks:
            parse_results = await asyncio.gather(*parse_tasks, return_exceptions=True)

            # Raccogli chunk da tutti i documenti
            for result in parse_results:
                if isinstance(result, list):
                    all_chunks.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Errore parsing: {result}")

        logger.info(f"Parsing completato: {len(all_chunks)} chunk estratti")

        # Step 3: Deduplicazione
        unique_chunks = self._deduplicate_chunks(all_chunks)
        logger.info(f"Deduplicazione: {len(unique_chunks)} chunk unici")

        return unique_chunks

    async def ingest_from_directory(self, directory: str) -> List[DocumentChunk]:
        """
        Ingestione da directory locale (per file PDF/HTML)

        Args:
            directory: Percorso della directory

        Returns:
            Lista di chunk processati
        """
        directory_path = Path(directory)
        if not directory_path.exists():
            raise ValueError(f"Directory non trovata: {directory}")

        logger.info(f"Ingestione da directory: {directory}")

        all_chunks = []
        supported_extensions = self.settings.ingest.supported_extensions

        # Trova tutti i file supportati
        files = []
        for ext in supported_extensions:
            files.extend(directory_path.rglob(f"*{ext}"))

        logger.info(f"Trovati {len(files)} file da processare")

        # Process files in parallel
        parse_tasks = []
        for file_path in files:
            if file_path.suffix.lower() == ".pdf":
                task = self._parse_pdf_file(str(file_path))
            elif file_path.suffix.lower() in [".html", ".htm"]:
                task = self._parse_html_file(str(file_path))
            else:
                continue

            parse_tasks.append(task)

        if parse_tasks:
            parse_results = await asyncio.gather(*parse_tasks, return_exceptions=True)

            for result in parse_results:
                if isinstance(result, list):
                    all_chunks.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Errore parsing file: {result}")

        # Deduplicazione
        unique_chunks = self._deduplicate_chunks(all_chunks)
        logger.info(f"Ingestione directory completata: {len(unique_chunks)} chunk")

        return unique_chunks

    async def _parse_html_document(
        self, crawl_result: CrawlResult
    ) -> List[DocumentChunk]:
        """
        Parse documento HTML da risultato crawling con estrazione immagini.
        Supporta streaming batch processing per documenti grandi.
        """
        try:
            sections, metadata = self.html_parser.parse_from_url(
                crawl_result.url, crawl_result.content
            )

            logger.info(f"Estratte {len(sections)} sezioni da {crawl_result.url}")

            # Verifica se usare streaming batch processing
            use_streaming = (
                self.settings.ingest.enable_streaming_ingest
                and len(sections) > self.settings.ingest.sections_batch_size
            )

            if use_streaming:
                logger.info(
                    f"Documento grande ({len(sections)} sezioni), uso streaming batch processing"
                )
                # Estrai immagini una volta per tutte (se abilitato)
                images_metadata = await self._extract_images_from_sections(
                    sections, metadata
                )

                # Processa sezioni in batch
                all_chunks = await self._process_sections_in_batches(
                    sections, metadata, images_metadata
                )
                return all_chunks
            else:
                # Modalità standard per documenti piccoli
                logger.info(
                    f"Documento piccolo ({len(sections)} sezioni), processing standard"
                )
                return await self._process_sections_standard(sections, metadata)

        except Exception as e:
            logger.error(f"Errore parsing HTML {crawl_result.url}: {e}", exc_info=True)
            return []

    async def _extract_images_from_sections(
        self, sections: List, metadata: Dict
    ) -> List:
        """Estrae immagini da tutte le sezioni"""
        images_metadata = []
        if not self.image_service:
            return images_metadata

        logger.info(f"ImageService attivo, inizio estrazione immagini da HTML")
        try:
            # Raccogli tutte le figure da tutte le sezioni
            all_figures = []
            for section in sections:
                if hasattr(section, "figures") and section.figures:
                    all_figures.extend(section.figures)

            logger.info(f"Raccolte {len(all_figures)} figure totali dalle sezioni")

            if all_figures:
                images_metadata = (
                    await self.image_service.download_and_save_html_images(
                        all_figures, metadata["source_url"]
                    )
                )
                logger.info(f"Scaricate {len(images_metadata)} immagini da HTML")
        except Exception as e:
            logger.error(f"Errore estrazione immagini da HTML: {e}", exc_info=True)

        return images_metadata

    async def _process_sections_standard(
        self, sections: List, metadata: Dict
    ) -> List[DocumentChunk]:
        """Processa sezioni in modalità standard (tutto in memoria)"""
        images_metadata = await self._extract_images_from_sections(sections, metadata)

        chunks = []
        figure_index = 0

        for section in sections:
            chunk = self._create_chunk_from_html_section(section, metadata)
            if chunk:
                # Associa immagini al chunk
                if images_metadata and hasattr(section, "figures"):
                    num_figures = len(section.figures)
                    section_images = images_metadata[
                        figure_index : figure_index + num_figures
                    ]
                    self._associate_images_to_chunk(chunk, section_images)
                    figure_index += num_figures

                chunks.append(chunk)

        return chunks

    async def _process_sections_in_batches(
        self, sections: List, metadata: Dict, images_metadata: List
    ) -> List[DocumentChunk]:
        """
        Processa sezioni in batch per ridurre uso memoria.
        Ogni batch viene processato e può essere indicizzato separatamente.
        """
        batch_size = self.settings.ingest.sections_batch_size
        total_sections = len(sections)
        all_chunks = []
        figure_index = 0

        logger.info(
            f"Inizio processing in batch: {total_sections} sezioni, batch_size={batch_size}"
        )

        # Dividi sezioni in batch
        for batch_start in range(0, total_sections, batch_size):
            batch_end = min(batch_start + batch_size, total_sections)
            batch_sections = sections[batch_start:batch_end]

            logger.info(
                f"Processing batch {batch_start // batch_size + 1}/{(total_sections + batch_size - 1) // batch_size}: sezioni {batch_start}-{batch_end}"
            )

            batch_chunks = []

            for section in batch_sections:
                chunk = self._create_chunk_from_html_section(section, metadata)
                if chunk:
                    # Associa immagini al chunk
                    if images_metadata and hasattr(section, "figures"):
                        num_figures = len(section.figures)
                        section_images = images_metadata[
                            figure_index : figure_index + num_figures
                        ]
                        self._associate_images_to_chunk(chunk, section_images)
                        figure_index += num_figures

                    batch_chunks.append(chunk)

            all_chunks.extend(batch_chunks)
            logger.info(
                f"Batch completato: {len(batch_chunks)} chunk creati, totale: {len(all_chunks)}"
            )

            # Piccola pausa per permettere al GC di liberare memoria
            await asyncio.sleep(0.01)

        logger.info(
            f"Processing in batch completato: {len(all_chunks)} chunk totali da {total_sections} sezioni"
        )
        return all_chunks

    def _associate_images_to_chunk(self, chunk: DocumentChunk, section_images: List):
        """Associa immagini a un chunk e arricchisce con testo OCR"""
        if not section_images:
            return

        chunk.metadata.image_ids = [img.id for img in section_images]

        # Aggiorna chunk_id nelle immagini
        for img in section_images:
            img.chunk_id = chunk.metadata.id

        # Arricchisci contenuto con testo OCR
        ocr_texts = [img.ocr_text for img in section_images if img.ocr_text]
        if ocr_texts:
            chunk.content += "\n\n[Testo estratto dalle immagini]\n" + "\n---\n".join(
                ocr_texts
            )
            logger.debug(f"Arricchito chunk con {len(ocr_texts)} testi OCR")

    async def _parse_html_file(self, file_path: str) -> List[DocumentChunk]:
        """Parse file HTML locale"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            sections, metadata = self.html_parser.parse_from_url(
                f"file://{file_path}", content
            )

            chunks = []
            for section in sections:
                chunk = self._create_chunk_from_html_section(section, metadata)
                if chunk:
                    chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"Errore parsing file HTML {file_path}: {e}")
            return []

    async def _parse_pdf_document(
        self, crawl_result: CrawlResult
    ) -> List[DocumentChunk]:
        """Parse documento PDF da risultato crawling"""
        try:
            # Crea directory temporanea cross-platform
            temp_dir = Path(tempfile.gettempdir()) / "rag_gestionale_pdfs"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Salva PDF temporaneo con nome univoco
            temp_file = temp_dir / f"{crawl_result.content_hash}.pdf"

            logger.info(f"Salvando PDF temporaneo in: {temp_file}")

            with open(temp_file, "wb") as f:
                # Riconverti da latin-1 a bytes
                f.write(crawl_result.content.encode("latin-1"))

            logger.info(f"PDF salvato, inizio parsing da {temp_file}")
            chunks = await self._parse_pdf_file(str(temp_file))
            logger.info(f"Parsing completato, ottenuti {len(chunks)} chunk dal PDF")

            # Cleanup
            temp_file.unlink(missing_ok=True)

            return chunks

        except Exception as e:
            logger.error(f"Errore parsing PDF {crawl_result.url}: {e}", exc_info=True)
            return []

    async def _parse_pdf_file(self, file_path: str) -> List[DocumentChunk]:
        """Parse file PDF con estrazione immagini"""
        try:
            sections, metadata = self.pdf_parser.parse_from_path(file_path)

            # Estrai immagini se abilitato
            images_metadata = []
            if self.image_service:
                try:
                    import fitz

                    doc = fitz.open(file_path)
                    images_metadata = (
                        await self.image_service.extract_and_save_pdf_images(
                            doc, metadata["source_url"]
                        )
                    )
                    doc.close()
                    logger.info(
                        f"Estratte {len(images_metadata)} immagini da PDF {file_path}"
                    )
                except Exception as e:
                    logger.error(f"Errore estrazione immagini da PDF: {e}")

            # Crea chunk dalle sezioni
            chunks = []
            for section in sections:
                chunk = self._create_chunk_from_pdf_section(section, metadata)
                if chunk:
                    # Associa immagini al chunk in base al range di pagine
                    if images_metadata:
                        section_images = [
                            img
                            for img in images_metadata
                            if img.page_number
                            and section.page_start
                            <= img.page_number
                            <= section.page_end
                        ]

                        if section_images:
                            # Aggiorna image_ids nel chunk
                            chunk.metadata.image_ids = [
                                img.id for img in section_images
                            ]

                            # Aggiorna chunk_id nelle immagini
                            for img in section_images:
                                img.chunk_id = chunk.metadata.id

                            # Arricchisci contenuto con testo OCR
                            ocr_texts = [
                                img.ocr_text for img in section_images if img.ocr_text
                            ]
                            if ocr_texts:
                                chunk.content += (
                                    "\n\n[Testo estratto dalle immagini]\n"
                                    + "\n---\n".join(ocr_texts)
                                )
                                logger.debug(
                                    f"Arricchito chunk con {len(ocr_texts)} testi OCR"
                                )

                            logger.debug(
                                f"Associati {len(section_images)} immagini al chunk {chunk.metadata.id}"
                            )

                    chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"Errore parsing PDF {file_path}: {e}")
            return []

    def _create_chunk_from_html_section(
        self, section: HTMLSection, doc_metadata: Dict
    ) -> Optional[DocumentChunk]:
        """Crea DocumentChunk da HTMLSection"""
        try:
            # Verifica che sia un'istanza di HTMLSection
            if not hasattr(section, "error_codes"):
                logger.warning(f"Oggetto section non valido: {type(section)}")
                return None

            # Combina titolo e contenuto
            full_content = f"{section.title}\n\n{section.content}"

            # Se ci sono tabelle, aggiungile
            if hasattr(section, "tables") and section.tables:
                full_content += "\n\n" + "\n\n".join(section.tables)

            # Metadati del chunk
            chunk_metadata = ChunkMetadata(
                id=f"{compute_content_hash(doc_metadata['source_url'])}#{section.section_id}",
                title=section.title,
                breadcrumbs=extract_breadcrumbs(section.section_id),
                section_level=section.level,
                section_path=section.section_id,
                content_type=section.content_type,
                version=doc_metadata.get("version", "1.0"),
                module=doc_metadata.get("module", "Generale"),
                param_name=self._extract_param_name(section),
                ui_path=getattr(section, "ui_path", None),
                error_code=section.error_codes[0] if section.error_codes else None,
                source_url=doc_metadata["source_url"],
                source_format=SourceFormat.HTML,
                anchor=getattr(section, "anchor", None),
                lang="it",
                hash=compute_content_hash(full_content),
                updated_at=datetime.now(),
            )

            return DocumentChunk(content=full_content, metadata=chunk_metadata)

        except Exception as e:
            logger.error(f"Errore creazione chunk HTML: {e}")
            return None

    def _create_chunk_from_pdf_section(
        self, section: PDFSection, doc_metadata: Dict
    ) -> Optional[DocumentChunk]:
        """Crea DocumentChunk da PDFSection"""
        try:
            # Combina titolo e contenuto
            full_content = f"{section.title}\n\n{section.content}"

            # Se ci sono tabelle, aggiungile
            if section.tables:
                full_content += "\n\n" + "\n\n".join(section.tables)

            # Metadati del chunk
            chunk_metadata = ChunkMetadata(
                id=f"{compute_content_hash(doc_metadata['source_url'])}#page{section.page_start}-{section.page_end}",
                title=section.title,
                breadcrumbs=extract_breadcrumbs(section.title),
                section_level=section.level,
                section_path=f"page{section.page_start}-{section.page_end}",
                content_type=section.content_type,
                version=doc_metadata.get("version", "1.0"),
                module=doc_metadata.get("module", "Generale"),
                param_name=self._extract_param_name_from_text(section.content),
                error_code=section.error_codes[0] if section.error_codes else None,
                source_url=doc_metadata["source_url"],
                source_format=SourceFormat.PDF,
                page_range=[section.page_start, section.page_end],
                lang="it",
                hash=compute_content_hash(full_content),
                updated_at=datetime.now(),
            )

            return DocumentChunk(content=full_content, metadata=chunk_metadata)

        except Exception as e:
            logger.error(f"Errore creazione chunk PDF: {e}")
            return None

    def _extract_param_name(self, section) -> Optional[str]:
        """Estrae nome parametro dalla sezione se è un parametro"""
        if (
            hasattr(section, "content_type")
            and section.content_type == ContentType.PARAMETER
        ):
            # Cerca pattern nel titolo per nome parametro
            import re

            patterns = [
                r"Parametro\s+([^:\n]+)",
                r"Impostazione\s+([^:\n]+)",
                r"Campo\s+([^:\n]+)",
            ]

            text = (
                section.title
                + " "
                + (section.content[:200] if hasattr(section, "content") else "")
            )

            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()

        return None

    def _extract_param_name_from_text(self, text: str) -> Optional[str]:
        """Estrae nome parametro dal testo"""
        import re

        patterns = [
            r"Parametro\s+([^:\n]+)",
            r"Impostazione\s+([^:\n]+)",
            r"Campo\s+([^:\n]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:200], re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _deduplicate_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Rimuove chunk duplicati basandosi sull'hash del contenuto"""
        seen_hashes = set()
        unique_chunks = []

        for chunk in chunks:
            content_hash = chunk.metadata.hash
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_chunks.append(chunk)

        return unique_chunks

    async def get_processing_stats(self) -> Dict:
        """Statistiche del processing"""
        return {
            "processed_documents": len(self.processed_hashes),
            "supported_formats": self.settings.ingest.supported_extensions,
            "allowed_domains": self.settings.allowed_domains,
            "chunking_config": {
                "parent_max_tokens": self.settings.chunking.parent_max_tokens,
                "child_proc_max_tokens": self.settings.chunking.child_proc_max_tokens,
                "child_param_max_tokens": self.settings.chunking.child_param_max_tokens,
            },
        }


# Utility functions per uso rapido
async def ingest_urls(urls: List[str]) -> List[DocumentChunk]:
    """Utility per ingestione rapida da URL"""
    coordinator = IngestionCoordinator()
    return await coordinator.ingest_from_urls(urls)


async def ingest_directory(directory: str) -> List[DocumentChunk]:
    """Utility per ingestione rapida da directory"""
    coordinator = IngestionCoordinator()
    return await coordinator.ingest_from_directory(directory)
