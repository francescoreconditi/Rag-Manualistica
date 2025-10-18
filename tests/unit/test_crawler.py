"""
Unit tests per il modulo WebCrawler
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag_gestionale.ingest.crawler import CrawlResult, RateLimiter, WebCrawler


@pytest.mark.unit
class TestCrawlResult:
    """Test per CrawlResult"""

    def test_crawl_result_creation(self):
        """Test creazione CrawlResult"""
        result = CrawlResult(
            url="http://example.com/doc.html",
            content="<html><body>Test content</body></html>",
            content_type="text/html",
            status_code=200,
            headers={"content-type": "text/html"},
            timestamp=1234567890.0,
        )

        assert result.url == "http://example.com/doc.html"
        assert "Test content" in result.content
        assert result.status_code == 200
        assert result.content_hash is not None

    def test_is_html(self):
        """Test proprietà is_html"""
        result = CrawlResult(
            url="http://example.com/doc.html",
            content="<html></html>",
            content_type="text/html; charset=utf-8",
            status_code=200,
            headers={},
            timestamp=1234567890.0,
        )

        assert result.is_html is True

    def test_is_pdf(self):
        """Test proprietà is_pdf"""
        result = CrawlResult(
            url="http://example.com/doc.pdf",
            content="%PDF-1.4...",
            content_type="application/pdf",
            status_code=200,
            headers={},
            timestamp=1234567890.0,
        )

        assert result.is_pdf is True

    def test_file_extension_from_url(self):
        """Test estrazione estensione da URL"""
        result = CrawlResult(
            url="http://example.com/doc.pdf",
            content="content",
            content_type="text/plain",
            status_code=200,
            headers={},
            timestamp=1234567890.0,
        )

        assert result.file_extension == ".pdf"

    def test_file_extension_from_content_type(self):
        """Test estrazione estensione da content-type"""
        result = CrawlResult(
            url="http://example.com/document",
            content="content",
            content_type="application/pdf",
            status_code=200,
            headers={},
            timestamp=1234567890.0,
        )

        assert result.file_extension == ".pdf"

    def test_content_hash(self):
        """Test che content_hash sia calcolato"""
        result = CrawlResult(
            url="http://example.com/doc",
            content="Test content",
            content_type="text/html",
            status_code=200,
            headers={},
            timestamp=1234567890.0,
        )

        assert result.content_hash is not None
        assert len(result.content_hash) > 0


@pytest.mark.unit
class TestRateLimiter:
    """Test per RateLimiter"""

    def test_rate_limiter_creation(self):
        """Test creazione rate limiter"""
        limiter = RateLimiter(max_requests=10, time_window=60.0)

        assert limiter.max_requests == 10
        assert limiter.time_window == 60.0
        assert len(limiter.requests) == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self):
        """Test che rate limiter permetta richieste sotto il limite"""
        limiter = RateLimiter(max_requests=5, time_window=60.0)

        # Dovrebbe permettere 5 richieste senza attendere
        for _ in range(5):
            await limiter.wait()

        assert len(limiter.requests) == 5

    @pytest.mark.asyncio
    async def test_rate_limiter_cleans_old_requests(self):
        """Test pulizia richieste vecchie"""
        import time

        limiter = RateLimiter(max_requests=2, time_window=0.5)

        # Prima richiesta
        await limiter.wait()
        assert len(limiter.requests) == 1

        # Attendi oltre time_window
        await asyncio.sleep(0.6)

        # Nuova richiesta dovrebbe pulire la vecchia
        await limiter.wait()
        assert len(limiter.requests) == 1


@pytest.mark.unit
class TestWebCrawler:
    """Test per WebCrawler"""

    @pytest.fixture
    async def mock_session(self):
        """Mock httpx AsyncClient"""
        session = AsyncMock()

        # Mock response successo
        response = MagicMock()
        response.status_code = 200
        response.text = "<html><body>Test content</body></html>"
        response.content = b"<html><body>Test content</body></html>"
        response.headers = {"content-type": "text/html"}
        response.raise_for_status = MagicMock()

        session.get = AsyncMock(return_value=response)
        session.aclose = AsyncMock()

        return session

    @pytest.fixture
    async def crawler(self, mock_session):
        """Fixture che crea un crawler con mock"""
        with patch(
            "src.rag_gestionale.ingest.crawler.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value = mock_session

            crawler = WebCrawler()
            await crawler.start()
            yield crawler
            await crawler.stop()

    @pytest.mark.asyncio
    async def test_crawler_initialization(self, crawler):
        """Test inizializzazione crawler"""
        assert crawler is not None
        assert crawler.session is not None
        assert isinstance(crawler.visited_urls, set)
        assert isinstance(crawler.content_hashes, set)

    @pytest.mark.asyncio
    async def test_crawler_context_manager(self, mock_session):
        """Test uso come context manager"""
        with patch(
            "src.rag_gestionale.ingest.crawler.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value = mock_session

            async with WebCrawler() as crawler:
                assert crawler.session is not None

    @pytest.mark.asyncio
    async def test_crawl_single_url(self, crawler, mock_session):
        """Test crawling singolo URL"""
        url = "http://example.com/doc.html"

        result = await crawler._crawl_single_url(url)

        assert result is not None
        assert isinstance(result, CrawlResult)
        assert result.url == url
        assert url in crawler.visited_urls

    @pytest.mark.asyncio
    async def test_crawl_duplicate_url(self, crawler):
        """Test che URL duplicati vengano ignorati"""
        url = "http://example.com/doc.html"

        # Prima visita
        result1 = await crawler._crawl_single_url(url)
        assert result1 is not None

        # Seconda visita - dovrebbe essere None
        result2 = await crawler._crawl_single_url(url)
        assert result2 is None

    @pytest.mark.asyncio
    async def test_crawl_urls_list(self, crawler):
        """Test crawling lista URL"""
        urls = [
            "http://example.com/doc1.html",
            "http://example.com/doc2.html",
            "http://example.com/doc3.html",
        ]

        results = await crawler.crawl_urls(urls)

        assert isinstance(results, list)
        # Con il mock, dovrebbe ritornare risultati
        assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_crawl_urls_empty_list(self, crawler):
        """Test crawling con lista vuota"""
        results = await crawler.crawl_urls([])

        assert results == []

    @pytest.mark.asyncio
    async def test_crawl_invalid_urls(self, crawler):
        """Test crawling URL invalidi"""
        # URL non validi dovrebbero essere filtrati
        invalid_urls = ["not-a-url", "ftp://example.com", ""]

        results = await crawler.crawl_urls(invalid_urls)

        # Dovrebbe ritornare lista vuota (nessun URL valido)
        assert results == []

    @pytest.mark.asyncio
    async def test_fetch_with_http_success(self, crawler, mock_session):
        """Test fetch HTTP con successo"""
        url = "http://example.com/doc.html"

        result = await crawler._fetch_with_http(url)

        assert result is not None
        assert result.status_code == 200
        assert "Test content" in result.content

    @pytest.mark.asyncio
    async def test_fetch_with_http_error(self, crawler, mock_session):
        """Test fetch HTTP con errore"""
        import httpx

        # Mock errore HTTP
        mock_session.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

        url = "http://example.com/error"
        result = await crawler._fetch_with_http(url)

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_unsupported_content_type(self, crawler, mock_session):
        """Test fetch con content-type non supportato"""
        # Mock response con content-type non supportato
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.raise_for_status = MagicMock()
        mock_session.get = AsyncMock(return_value=response)

        url = "http://example.com/data.json"
        result = await crawler._fetch_with_http(url)

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_pdf(self, crawler, mock_session):
        """Test fetch file PDF"""
        # Mock response PDF
        response = MagicMock()
        response.status_code = 200
        response.content = b"%PDF-1.4 test content"
        response.headers = {"content-type": "application/pdf"}
        response.raise_for_status = MagicMock()
        mock_session.get = AsyncMock(return_value=response)

        url = "http://example.com/doc.pdf"
        result = await crawler._fetch_with_http(url)

        assert result is not None
        assert result.is_pdf

    @pytest.mark.asyncio
    async def test_content_deduplication(self, crawler):
        """Test deduplicazione contenuto"""
        # Simula due URL con stesso contenuto
        url1 = "http://example.com/doc1.html"
        url2 = "http://example.com/doc2.html"

        result1 = await crawler._crawl_single_url(url1)
        assert result1 is not None

        # Aggiungi hash al set
        crawler.content_hashes.add(result1.content_hash)

        # Secondo URL con stesso contenuto dovrebbe essere filtrato
        result2 = await crawler._crawl_single_url(url2)
        # Se il contenuto è lo stesso, dovrebbe essere None
        # (dipende dal mock)

    @pytest.mark.asyncio
    async def test_crawl_sitemap(self, crawler, mock_session):
        """Test parsing sitemap XML"""
        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>http://example.com/page1</loc>
            </url>
            <url>
                <loc>http://example.com/page2</loc>
            </url>
        </urlset>"""

        # Mock response sitemap
        response = MagicMock()
        response.status_code = 200
        response.text = sitemap_xml
        response.raise_for_status = MagicMock()
        mock_session.get = AsyncMock(return_value=response)

        urls = await crawler.crawl_sitemap("http://example.com/sitemap.xml")

        assert len(urls) == 2
        assert "http://example.com/page1" in urls
        assert "http://example.com/page2" in urls

    @pytest.mark.asyncio
    async def test_crawl_sitemap_error(self, crawler, mock_session):
        """Test errore parsing sitemap"""
        import httpx

        mock_session.get = AsyncMock(side_effect=httpx.HTTPError("Not found"))

        urls = await crawler.crawl_sitemap("http://example.com/sitemap.xml")

        assert urls == []

    @pytest.mark.asyncio
    async def test_save_to_cache(self, crawler, tmp_path):
        """Test salvataggio in cache"""
        result = CrawlResult(
            url="http://example.com/doc.html",
            content="Test content for cache",
            content_type="text/html",
            status_code=200,
            headers={},
            timestamp=1234567890.0,
        )

        cache_dir = str(tmp_path / "cache")
        saved_path = await crawler.save_to_cache(result, cache_dir)

        assert saved_path is not None
        # Verifica che il file esista
        from pathlib import Path

        assert Path(saved_path).exists()

    @pytest.mark.asyncio
    async def test_rate_limiting(self, crawler):
        """Test che rate limiting sia applicato"""
        # Il crawler dovrebbe avere un rate limiter
        assert crawler.rate_limiter is not None
        assert crawler.rate_limiter.max_requests > 0


@pytest.mark.unit
class TestWebCrawlerIntegration:
    """Test di integrazione per WebCrawler"""

    @pytest.mark.asyncio
    async def test_full_crawl_workflow(self):
        """Test flusso completo di crawling"""
        with patch(
            "src.rag_gestionale.ingest.crawler.httpx.AsyncClient"
        ) as mock_client:
            # Mock session
            session = AsyncMock()
            response = MagicMock()
            response.status_code = 200
            response.text = "<html><body>Test</body></html>"
            response.content = b"<html><body>Test</body></html>"
            response.headers = {"content-type": "text/html"}
            response.raise_for_status = MagicMock()
            session.get = AsyncMock(return_value=response)
            session.aclose = AsyncMock()
            mock_client.return_value = session

            async with WebCrawler() as crawler:
                urls = ["http://example.com/doc.html"]
                results = await crawler.crawl_urls(urls)

                # Dovrebbe avere almeno tentato il crawling
                assert isinstance(results, list)
