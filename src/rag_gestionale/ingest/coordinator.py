"""
Coordinatore del sistema di ingestione.
Orchestrazione di crawling, parsing e preprocessing per scalabilità massiva.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

from ..core.models import DocumentChunk, ChunkMetadata, ContentType, SourceFormat
from ..core.utils import compute_content_hash, extract_breadcrumbs
from ..config.settings import get_settings
from .crawler import WebCrawler, CrawlResult
from .html_parser import HTMLParser, HTMLSection
from .pdf_parser import PDFParser, PDFSection


class IngestionCoordinator:
    """Coordinatore principale per l'ingestione di documenti"""

    def __init__(self):
        self.settings = get_settings()
        self.html_parser = HTMLParser()
        self.pdf_parser = PDFParser()
        self.processed_hashes: set = set()

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
        """Parse documento HTML da risultato crawling"""
        try:
            sections, metadata = self.html_parser.parse_from_url(
                crawl_result.url, crawl_result.content
            )

            chunks = []
            for section in sections:
                chunk = self._create_chunk_from_html_section(section, metadata)
                if chunk:
                    chunks.append(chunk)

            return chunks

        except Exception as e:
            logger.error(f"Errore parsing HTML {crawl_result.url}: {e}")
            return []

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
            # Salva PDF temporaneo
            temp_file = f"/tmp/claude/{crawl_result.content_hash}.pdf"
            Path(temp_file).parent.mkdir(parents=True, exist_ok=True)

            with open(temp_file, "wb") as f:
                # Riconverti da latin-1 a bytes
                f.write(crawl_result.content.encode("latin-1"))

            chunks = await self._parse_pdf_file(temp_file)

            # Cleanup
            Path(temp_file).unlink(missing_ok=True)

            return chunks

        except Exception as e:
            logger.error(f"Errore parsing PDF {crawl_result.url}: {e}")
            return []

    async def _parse_pdf_file(self, file_path: str) -> List[DocumentChunk]:
        """Parse file PDF"""
        try:
            sections, metadata = self.pdf_parser.parse_from_path(file_path)

            chunks = []
            for section in sections:
                chunk = self._create_chunk_from_pdf_section(section, metadata)
                if chunk:
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
