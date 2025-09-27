"""
Sistema di crawling per documenti di gestionali.
Include throttling, whitelisting domini e gestione errori robusti.
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import aiofiles
import httpx
from loguru import logger
# from playwright.async_api import async_playwright  # Disabilitato temporaneamente

from ..config.settings import get_settings
from ..core.utils import is_valid_url, compute_content_hash


class CrawlResult:
    """Risultato del crawling di un URL"""

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
        # Prima dall'URL
        parsed = urlparse(self.url)
        path = Path(parsed.path)
        if path.suffix:
            return path.suffix.lower()

        # Poi dal content-type
        if self.is_pdf:
            return ".pdf"
        elif self.is_html:
            return ".html"

        return ""


class WebCrawler:
    """Crawler web asincrono per documenti di gestionali"""

    def __init__(self):
        self.settings = get_settings()
        self.visited_urls: Set[str] = set()
        self.content_hashes: Set[str] = set()
        self.session: Optional[httpx.AsyncClient] = None
        self.browser = None
        self.rate_limiter = RateLimiter(
            max_requests=self.settings.ingest.max_concurrent_requests,
            time_window=60.0,  # 1 minuto
        )

    async def __aenter__(self):
        """Context manager entry"""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.stop()

    async def start(self):
        """Inizializza il crawler"""
        # HTTP client
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": self.settings.ingest.user_agent},
            follow_redirects=True,
        )

        # Browser per JS-heavy pages (disabilitato temporaneamente)
        # playwright = await async_playwright().start()
        # self.browser = await playwright.chromium.launch(headless=True)
        self.browser = None  # Disabilitato per ora

        logger.info("Crawler inizializzato")

    async def stop(self):
        """Chiude il crawler"""
        if self.session:
            await self.session.aclose()

        if self.browser:
            await self.browser.close()

        logger.info("Crawler fermato")

    async def crawl_urls(self, urls: List[str]) -> List[CrawlResult]:
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
            url for url in urls if is_valid_url(url, self.settings.allowed_domains)
        ]

        if not valid_urls:
            logger.warning("Nessun URL valido trovato per il crawling")
            return results

        logger.info(f"Avvio crawling di {len(valid_urls)} URL")

        # Processa in batch per controllo concorrenza
        semaphore = asyncio.Semaphore(self.settings.ingest.max_concurrent_requests)

        async def crawl_single(url: str) -> Optional[CrawlResult]:
            async with semaphore:
                return await self._crawl_single_url(url)

        # Esegui crawling concorrente
        tasks = [crawl_single(url) for url in valid_urls]
        crawl_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filtra risultati validi
        for result in crawl_results:
            if isinstance(result, CrawlResult):
                results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Errore durante crawling: {result}")

        logger.info(f"Crawling completato: {len(results)} documenti scaricati")
        return results

    async def _crawl_single_url(self, url: str) -> Optional[CrawlResult]:
        """Crawl di un singolo URL"""
        if url in self.visited_urls:
            logger.debug(f"URL già visitato: {url}")
            return None

        try:
            # Rate limiting
            await self.rate_limiter.wait()

            # Delay tra richieste
            if self.settings.ingest.request_delay_ms > 0:
                await asyncio.sleep(self.settings.ingest.request_delay_ms / 1000)

            logger.debug(f"Crawling: {url}")

            # Prova prima con HTTP client
            result = await self._fetch_with_http(url)

            # Se fallisce o è JS-heavy, usa browser
            if not result and self.browser:
                result = await self._fetch_with_browser(url)

            if result:
                self.visited_urls.add(url)

                # Controllo deduplicazione
                if result.content_hash in self.content_hashes:
                    logger.debug(f"Contenuto duplicato per {url}")
                    return None

                self.content_hashes.add(result.content_hash)
                logger.debug(f"Scaricato {url} ({len(result.content)} chars)")

            return result

        except Exception as e:
            logger.error(f"Errore crawling {url}: {e}")
            return None

    async def _fetch_with_http(self, url: str) -> Optional[CrawlResult]:
        """Fetch con HTTP client"""
        try:
            response = await self.session.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            # Controlla se è un tipo supportato
            if not any(
                ct in content_type.lower()
                for ct in ["text/html", "application/pdf", "text/plain"]
            ):
                logger.debug(f"Content-type non supportato per {url}: {content_type}")
                return None

            # Per PDF, mantieni bytes
            if "application/pdf" in content_type.lower():
                content = response.content.decode("latin-1")  # Preserva bytes
            else:
                content = response.text

            return CrawlResult(
                url=url,
                content=content,
                content_type=content_type,
                status_code=response.status_code,
                headers=dict(response.headers),
                timestamp=time.time(),
            )

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error per {url}: {e}")
            return None

    async def _fetch_with_browser(self, url: str) -> Optional[CrawlResult]:
        """Fetch con browser Playwright per pagine JS-heavy"""
        try:
            context = await self.browser.new_context()
            page = await context.new_page()

            # Blocca risorse non necessarie per velocità
            await page.route(
                "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}",
                lambda route: route.abort(),
            )

            response = await page.goto(url, wait_until="networkidle")

            if not response or response.status >= 400:
                return None

            content = await page.content()
            content_type = "text/html"

            await context.close()

            return CrawlResult(
                url=url,
                content=content,
                content_type=content_type,
                status_code=response.status,
                headers={},
                timestamp=time.time(),
            )

        except Exception as e:
            logger.warning(f"Browser error per {url}: {e}")
            return None

    async def crawl_sitemap(self, sitemap_url: str) -> List[str]:
        """
        Estrae URL da una sitemap XML

        Args:
            sitemap_url: URL della sitemap

        Returns:
            Lista di URL estratti
        """
        try:
            response = await self.session.get(sitemap_url)
            response.raise_for_status()

            import xml.etree.ElementTree as ET

            root = ET.fromstring(response.text)

            # Namespace per sitemap
            ns = {"sitemap": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            urls = []
            for url_elem in root.findall(".//sitemap:url", ns):
                loc = url_elem.find("sitemap:loc", ns)
                if loc is not None and loc.text:
                    urls.append(loc.text)

            logger.info(f"Estratti {len(urls)} URL da sitemap {sitemap_url}")
            return urls

        except Exception as e:
            logger.error(f"Errore parsing sitemap {sitemap_url}: {e}")
            return []

    async def save_to_cache(self, result: CrawlResult, cache_dir: str) -> str:
        """
        Salva il risultato nella cache locale

        Args:
            result: Risultato del crawling
            cache_dir: Directory della cache

        Returns:
            Percorso del file salvato
        """
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)

        # Nome file basato su hash del contenuto
        filename = f"{result.content_hash}{result.file_extension}"
        file_path = cache_path / filename

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(result.content)

        return str(file_path)


class RateLimiter:
    """Rate limiter semplice per controllo richieste"""

    def __init__(self, max_requests: int, time_window: float):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []

    async def wait(self):
        """Attende se necessario per rispettare il rate limit"""
        now = time.time()

        # Rimuovi richieste vecchie
        self.requests = [
            req_time for req_time in self.requests if now - req_time < self.time_window
        ]

        # Se abbiamo raggiunto il limite, attendi
        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.requests.append(now)


# Utility function per crawling rapido
async def crawl_documents(urls: List[str]) -> List[CrawlResult]:
    """
    Utility per crawling rapido di documenti

    Args:
        urls: Lista di URL da crawlare

    Returns:
        Lista di risultati
    """
    async with WebCrawler() as crawler:
        return await crawler.crawl_urls(urls)
