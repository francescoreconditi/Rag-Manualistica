"""
End-to-end tests per il flusso completo di ingestion e ricerca
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.rag_gestionale.api.main import app
from src.rag_gestionale.core.models import QueryType, RAGResponse


@pytest.mark.e2e
@pytest.mark.slow
class TestFullPipeline:
    """Test end-to-end per il flusso completo"""

    @pytest.fixture
    async def mock_full_system(self, sample_chunks_list, sample_search_results):
        """Mock del sistema completo"""

        async def mock_get_components():
            components = MagicMock()

            # Storage per chunk indicizzati
            indexed_chunks = []

            # Mock ingestion coordinator
            coordinator = AsyncMock()
            coordinator.ingest_from_urls = AsyncMock(return_value=sample_chunks_list)
            coordinator.ingest_from_directory = AsyncMock(
                return_value=sample_chunks_list
            )
            components.ingestion_coordinator = coordinator

            # Mock retriever con stato
            retriever = AsyncMock()

            async def add_chunks_mock(chunks):
                indexed_chunks.extend(chunks)

            async def search_mock(query, top_k=10, filters=None, query_type=None):
                # Ritorna risultati solo se ci sono chunk indicizzati
                if indexed_chunks:
                    return sample_search_results[:top_k]
                return []

            retriever.add_chunks = AsyncMock(side_effect=add_chunks_mock)
            retriever.search = AsyncMock(side_effect=search_mock)
            retriever.query_classifier = MagicMock()
            retriever.query_classifier.classify_query = MagicMock(
                return_value=QueryType.GENERAL
            )
            components.retriever = retriever

            # Mock generator
            generator = AsyncMock()

            async def generate_response_mock(
                query, query_type, search_results, processing_time_ms
            ):
                if search_results:
                    return RAGResponse(
                        query=query,
                        query_type=query_type,
                        answer=f"Risposta generata per: {query}",
                        sources=search_results,
                        confidence=0.85,
                        processing_time_ms=processing_time_ms + 50,
                    )
                else:
                    return RAGResponse(
                        query=query,
                        query_type=query_type,
                        answer="Nessuna informazione trovata.",
                        sources=[],
                        confidence=0.0,
                        processing_time_ms=processing_time_ms + 50,
                    )

            generator.generate_response = AsyncMock(side_effect=generate_response_mock)
            components.generator = generator

            return components

        return mock_get_components

    @pytest.fixture
    async def client(self, mock_full_system):
        """Client HTTP per test E2E"""
        with (
            patch(
                "src.rag_gestionale.api.routers.ingest.get_components", mock_full_system
            ),
            patch(
                "src.rag_gestionale.api.routers.search.get_components", mock_full_system
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                yield client

    @pytest.mark.asyncio
    async def test_ingest_then_search(self, client):
        """Test flusso completo: ingest -> search"""
        # Step 1: Ingest documenti
        ingest_request = {"urls": ["http://example.com/manual.pdf"]}

        ingest_response = await client.post("/api/v1/ingest", json=ingest_request)

        assert ingest_response.status_code == 200
        ingest_data = ingest_response.json()
        assert ingest_data["status"] == "success"
        assert ingest_data["chunks_processed"] > 0

        # Step 2: Ricerca nei documenti indicizzati
        search_request = {"query": "come creare una fattura", "top_k": 5}

        search_response = await client.post("/api/v1/search", json=search_request)

        assert search_response.status_code == 200
        search_data = search_response.json()
        assert len(search_data["answer"]) > 0
        assert len(search_data["sources"]) > 0
        assert search_data["confidence"] > 0

    @pytest.mark.asyncio
    async def test_search_before_ingest(self, client):
        """Test ricerca prima di qualsiasi ingestione"""
        # Ricerca senza aver ingerito documenti
        search_request = {"query": "test query", "top_k": 5}

        search_response = await client.post("/api/v1/search", json=search_request)

        assert search_response.status_code == 200
        search_data = search_response.json()

        # Dovrebbe ritornare risultati vuoti o fallback
        # (dipende dall'implementazione del mock)

    @pytest.mark.asyncio
    async def test_multiple_ingests_then_search(self, client):
        """Test multiple ingestioni seguite da ricerca"""
        # Ingest 1
        ingest1 = {"urls": ["http://example.com/doc1.pdf"]}
        response1 = await client.post("/api/v1/ingest", json=ingest1)
        assert response1.status_code == 200

        # Ingest 2
        ingest2 = {"urls": ["http://example.com/doc2.pdf"]}
        response2 = await client.post("/api/v1/ingest", json=ingest2)
        assert response2.status_code == 200

        # Search
        search_request = {"query": "informazioni sui documenti", "top_k": 10}
        search_response = await client.post("/api/v1/search", json=search_request)

        assert search_response.status_code == 200
        search_data = search_response.json()
        assert len(search_data["answer"]) > 0

    @pytest.mark.asyncio
    async def test_ingest_search_different_query_types(self, client):
        """Test ricerca con diversi tipi di query dopo ingestione"""
        # Ingest
        ingest_request = {"urls": ["http://example.com/manual.pdf"]}
        await client.post("/api/v1/ingest", json=ingest_request)

        # Query procedure
        proc_request = {"query": "come creare fattura", "top_k": 5}
        proc_response = await client.post("/api/v1/search", json=proc_request)
        assert proc_response.status_code == 200

        # Query parameter
        param_request = {"query": "parametro IVA", "top_k": 5}
        param_response = await client.post("/api/v1/search", json=param_request)
        assert param_response.status_code == 200

        # Query error
        error_request = {"query": "errore ERR-001", "top_k": 5}
        error_response = await client.post("/api/v1/search", json=error_request)
        assert error_response.status_code == 200

    @pytest.mark.asyncio
    async def test_ingest_from_directory_then_search(self, client):
        """Test ingestione da directory seguita da ricerca"""
        # Ingest da directory
        ingest_request = {"directory": "/path/to/manuals"}
        ingest_response = await client.post("/api/v1/ingest", json=ingest_request)

        assert ingest_response.status_code == 200
        assert ingest_response.json()["status"] == "success"

        # Search
        search_request = {"query": "informazioni", "top_k": 5}
        search_response = await client.post("/api/v1/search", json=search_request)

        assert search_response.status_code == 200

    @pytest.mark.asyncio
    async def test_search_with_filters_after_ingest(self, client):
        """Test ricerca con filtri dopo ingestione"""
        # Ingest
        ingest_request = {"urls": ["http://example.com/manual.pdf"]}
        await client.post("/api/v1/ingest", json=ingest_request)

        # Search con filtri
        search_request = {
            "query": "fatturazione",
            "top_k": 5,
            "filters": {"module": "Fatturazione", "version": "1.0"},
        }
        search_response = await client.post("/api/v1/search", json=search_request)

        assert search_response.status_code == 200

    @pytest.mark.asyncio
    async def test_quality_of_results(self, client):
        """Test qualità dei risultati end-to-end"""
        # Ingest
        ingest_request = {"urls": ["http://example.com/manual.pdf"]}
        await client.post("/api/v1/ingest", json=ingest_request)

        # Search
        search_request = {"query": "come creare una fattura", "top_k": 5}
        search_response = await client.post("/api/v1/search", json=search_request)

        assert search_response.status_code == 200
        data = search_response.json()

        # Verifica qualità risposta
        assert len(data["answer"]) >= 50  # Risposta sufficientemente dettagliata
        assert 0.0 <= data["confidence"] <= 1.0
        assert data["processing_time_ms"] > 0

        # Verifica qualità fonti
        if data["sources"]:
            for source in data["sources"]:
                assert "chunk" in source
                assert "score" in source
                assert source["score"] > 0


@pytest.mark.e2e
@pytest.mark.slow
class TestErrorRecovery:
    """Test per recovery da errori nel flusso E2E"""

    @pytest.fixture
    async def client_with_errors(self, sample_chunks_list):
        """Client con mock che simulano errori"""

        async def mock_get_components_with_errors():
            components = MagicMock()

            # Coordinator che può fallire
            coordinator = AsyncMock()
            coordinator.ingest_from_urls = AsyncMock(
                side_effect=Exception("Ingest failed")
            )
            components.ingestion_coordinator = coordinator

            # Retriever normale
            retriever = AsyncMock()
            retriever.search = AsyncMock(return_value=[])
            retriever.query_classifier = MagicMock()
            retriever.query_classifier.classify_query = MagicMock(
                return_value=QueryType.GENERAL
            )
            components.retriever = retriever

            # Generator normale
            generator = AsyncMock()
            generator.generate_response = AsyncMock(
                return_value=RAGResponse(
                    query="test",
                    query_type=QueryType.GENERAL,
                    answer="Fallback",
                    sources=[],
                    confidence=0.0,
                    processing_time_ms=100,
                )
            )
            components.generator = generator

            return components

        with (
            patch(
                "src.rag_gestionale.api.routers.ingest.get_components",
                mock_get_components_with_errors,
            ),
            patch(
                "src.rag_gestionale.api.routers.search.get_components",
                mock_get_components_with_errors,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                yield client

    @pytest.mark.asyncio
    async def test_ingest_error_handling(self, client_with_errors):
        """Test gestione errori durante ingestione"""
        ingest_request = {"urls": ["http://example.com/doc.pdf"]}

        response = await client_with_errors.post("/api/v1/ingest", json=ingest_request)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_search_graceful_degradation(self, client_with_errors):
        """Test degradazione graceful durante ricerca"""
        search_request = {"query": "test query", "top_k": 5}

        response = await client_with_errors.post("/api/v1/search", json=search_request)

        # Dovrebbe comunque ritornare una risposta (anche se fallback)
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data


@pytest.mark.e2e
class TestPerformance:
    """Test di performance per il flusso E2E"""

    @pytest.fixture
    async def client(self, sample_chunks_list, sample_search_results):
        """Client per test di performance"""

        async def mock_get_components():
            components = MagicMock()

            # Fast mock implementations
            components.ingestion_coordinator = AsyncMock()
            components.ingestion_coordinator.ingest_from_urls = AsyncMock(
                return_value=sample_chunks_list
            )

            components.retriever = AsyncMock()
            components.retriever.add_chunks = AsyncMock()
            components.retriever.search = AsyncMock(return_value=sample_search_results)
            components.retriever.query_classifier = MagicMock()
            components.retriever.query_classifier.classify_query = MagicMock(
                return_value=QueryType.GENERAL
            )

            components.generator = AsyncMock()
            components.generator.generate_response = AsyncMock(
                return_value=RAGResponse(
                    query="test",
                    query_type=QueryType.GENERAL,
                    answer="Fast response",
                    sources=sample_search_results,
                    confidence=0.8,
                    processing_time_ms=50,
                )
            )

            return components

        with (
            patch(
                "src.rag_gestionale.api.routers.ingest.get_components",
                mock_get_components,
            ),
            patch(
                "src.rag_gestionale.api.routers.search.get_components",
                mock_get_components,
            ),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                yield client

    @pytest.mark.asyncio
    async def test_search_response_time(self, client):
        """Test tempo di risposta della ricerca"""
        import time

        request_data = {"query": "test query", "top_k": 5}

        start = time.time()
        response = await client.post("/api/v1/search", json=request_data)
        elapsed = (time.time() - start) * 1000  # ms

        assert response.status_code == 200
        # Il mock dovrebbe rispondere velocemente
        assert elapsed < 5000  # Meno di 5 secondi (molto permissivo per CI)

    @pytest.mark.asyncio
    async def test_ingest_response_time(self, client):
        """Test tempo di risposta dell'ingestione"""
        import time

        request_data = {"urls": ["http://example.com/doc.pdf"]}

        start = time.time()
        response = await client.post("/api/v1/ingest", json=request_data)
        elapsed = (time.time() - start) * 1000  # ms

        assert response.status_code == 200
        # Il mock dovrebbe rispondere velocemente
        assert elapsed < 5000  # Meno di 5 secondi
