"""
Crawler semplificato senza dipendenze complesse.
Usa solo httpx per il download di documenti.
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
from loguru import logger

from ..config.settings import get_settings
from ..core.utils import is_valid_url, compute_content_hash


class SimpleCrawlResult:
    """Risultato del crawling semplificato"""

    def __init__(
        self,
        url: str,
        content: str,
        content_type: str,
        status_code: int,
        headers: Dict[str, str],
        timestamp: float,
    ):
        self.url = url
        self.content = content
        self.content_type = content_type
        self.status_code = status_code
        self.headers = headers
        self.timestamp = timestamp
        self.content_hash = compute_content_hash(content)

    @property
    def is_html(self) -> bool:
        return "text/html" in self.content_type.lower()

    @property
    def is_pdf(self) -> bool:
        return "application/pdf" in self.content_type.lower()

    @property
    def file_extension(self) -> str:
        """Estrae l'estensione del file dall'URL o content-type"""
        parsed = urlparse(self.url)
        path = Path(parsed.path)
        if path.suffix:
            return path.suffix.lower()

        if self.is_pdf:
            return ".pdf"
        elif self.is_html:
            return ".html"

        return ""


class SimpleWebCrawler:
    """Crawler web semplificato per documenti di gestionali"""

    def __init__(self):
        self.settings = get_settings()
        self.visited_urls: Set[str] = set()
        self.content_hashes: Set[str] = set()
        self.session: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Context manager entry"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.stop()

    async def start(self):
        """Inizializza il crawler"""
        # HTTP client con timeout più lungo per documenti grandi
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0),
            headers={
                "User-Agent": self.settings.ingest.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

        logger.info("Simple crawler inizializzato")

    async def stop(self):
        """Chiude il crawler"""
        if self.session:
            await self.session.aclose()
        logger.info("Simple crawler fermato")

    async def crawl_urls(self, urls: List[str]) -> List[SimpleCrawlResult]:
        """
        Crawl di una lista di URL

        Args:
            urls: Lista di URL da processare

        Returns:
            Lista di risultati del crawling
        """
        results = []

        # Filtra URL validi
        valid_urls = [
            url
            for url in urls
            if is_valid_url(url, self.settings.allowed_domains)
        ]

        if not valid_urls:
            logger.warning("Nessun URL valido trovato per il crawling")
            return results

        logger.info(f"Avvio crawling di {len(valid_urls)} URL")

        # Processa URL uno alla volta per evitare sovraccarico
        for url in valid_urls:
            try:
                result = await self._crawl_single_url(url)
                if result:
                    results.append(result)
                    logger.info(f"✓ Scaricato: {url[:50]}...")

                # Piccolo delay tra richieste
                if self.settings.ingest.request_delay_ms > 0:
                    await asyncio.sleep(self.settings.ingest.request_delay_ms / 1000)

            except Exception as e:
                logger.error(f"Errore crawling {url}: {e}")
                continue

        logger.info(f"Crawling completato: {len(results)} documenti scaricati")
        return results

    async def _crawl_single_url(self, url: str) -> Optional[SimpleCrawlResult]:
        """Crawl di un singolo URL"""
        if url in self.visited_urls:
            logger.debug(f"URL già visitato: {url}")
            return None

        try:
            logger.debug(f"Scaricamento: {url}")

            # Fetch con HTTP client
            response = await self.session.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            # Controlla se è un tipo supportato
            supported_types = ["text/html", "text/plain", "application/pdf", "application/json"]
            if not any(ct in content_type.lower() for ct in supported_types):
                logger.warning(f"Content-type non supportato per {url}: {content_type}")
                return None

            # Per PDF, gestisci come bytes
            if "application/pdf" in content_type.lower():
                content = response.content.decode("latin-1", errors='ignore')
            else:
                # Per HTML e testo, usa encoding appropriato
                content = response.text

            # Verifica lunghezza minima
            if len(content) < self.settings.ingest.min_content_length:
                logger.debug(f"Contenuto troppo corto per {url}: {len(content)} chars")
                return None

            result = SimpleCrawlResult(
                url=url,
                content=content,
                content_type=content_type,
                status_code=response.status_code,
                headers=dict(response.headers),
                timestamp=time.time(),
            )

            # Marca come visitato
            self.visited_urls.add(url)

            # Controllo deduplicazione
            if result.content_hash in self.content_hashes:
                logger.debug(f"Contenuto duplicato per {url}")
                return None

            self.content_hashes.add(result.content_hash)
            logger.debug(f"Scaricato {url} ({len(content)} chars)")

            return result

        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} per {url}")
            return None
        except httpx.RequestError as e:
            logger.warning(f"Request error per {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Errore inatteso per {url}: {e}")
            return None


# Utility function per crawling rapido
async def simple_crawl_documents(urls: List[str]) -> List[SimpleCrawlResult]:
    """
    Utility per crawling rapido di documenti

    Args:
        urls: Lista di URL da crawlare

    Returns:
        Lista di risultati
    """
    async with SimpleWebCrawler() as crawler:
        return await crawler.crawl_urls(urls)