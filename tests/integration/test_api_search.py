"""
Integration tests per gli endpoint di ricerca
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.rag_gestionale.api.main import app
from src.rag_gestionale.core.models import RAGResponse, QueryType


@pytest.mark.integration
class TestSearchAPI:
    """Test per gli endpoint di ricerca"""

    @pytest.fixture
    async def mock_components(self, sample_search_results):
        """Mock dei componenti RAG"""
        components = MagicMock()

        # Mock retriever
        components.retriever = AsyncMock()
        components.retriever.search = AsyncMock(return_value=sample_search_results)
        components.retriever.query_classifier = MagicMock()
        components.retriever.query_classifier.classify_query = MagicMock(
            return_value=QueryType.GENERAL
        )

        # Mock generator
        components.generator = AsyncMock()
        components.generator.generate_response = AsyncMock(
            return_value=RAGResponse(
                query="test query",
                query_type=QueryType.GENERAL,
                answer="Questa è la risposta generata dal sistema.",
                sources=sample_search_results,
                confidence=0.85,
                processing_time_ms=150,
            )
        )

        return components

    @pytest.fixture
    async def client(self, mock_components):
        """Client HTTP per test"""
        with patch(
            "src.rag_gestionale.api.routers.search.get_components"
        ) as mock_get_components:
            mock_get_components.return_value = mock_components

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                yield client

    @pytest.mark.asyncio
    async def test_search_endpoint_basic(self, client):
        """Test ricerca base"""
        request_data = {
            "query": "come creare una fattura",
            "top_k": 5,
            "include_sources": True,
        }

        response = await client.post("/api/v1/search", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert "query" in data
        assert "answer" in data
        assert "sources" in data
        assert "confidence" in data
        assert data["query"] == request_data["query"]

    @pytest.mark.asyncio
    async def test_search_endpoint_with_filters(self, client):
        """Test ricerca con filtri"""
        request_data = {
            "query": "parametro IVA",
            "top_k": 10,
            "filters": {"module": "Contabilità", "version": "1.0"},
            "include_sources": True,
        }

        response = await client.post("/api/v1/search", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data

    @pytest.mark.asyncio
    async def test_search_endpoint_no_sources(self, client):
        """Test ricerca senza fonti nella risposta"""
        request_data = {
            "query": "test query",
            "top_k": 5,
            "include_sources": False,
        }

        response = await client.post("/api/v1/search", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert "sources" in data
        assert len(data["sources"]) == 0

    @pytest.mark.asyncio
    async def test_search_endpoint_empty_query(self, client):
        """Test ricerca con query vuota"""
        request_data = {
            "query": "",
            "top_k": 5,
        }

        response = await client.post("/api/v1/search", json=request_data)

        # Dovrebbe ritornare errore di validazione
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_endpoint_invalid_top_k(self, client):
        """Test ricerca con top_k invalido"""
        request_data = {
            "query": "test query",
            "top_k": 100,  # Oltre il limite
        }

        response = await client.post("/api/v1/search", json=request_data)

        # Dovrebbe ritornare errore di validazione
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_endpoint_no_results(self, client, mock_components):
        """Test ricerca senza risultati"""
        # Mock retriever che ritorna lista vuota
        mock_components.retriever.search = AsyncMock(return_value=[])

        request_data = {
            "query": "query senza risultati",
            "top_k": 5,
        }

        response = await client.post("/api/v1/search", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["confidence"] == 0.0
        assert len(data["sources"]) == 0

    @pytest.mark.asyncio
    async def test_search_endpoint_error_handling(self, client, mock_components):
        """Test gestione errori endpoint"""
        # Mock che solleva eccezione
        mock_components.retriever.search = AsyncMock(
            side_effect=Exception("Test error")
        )

        request_data = {
            "query": "test query",
            "top_k": 5,
        }

        response = await client.post("/api/v1/search", json=request_data)

        assert response.status_code == 500
        data = response.json()

        assert "detail" in data


@pytest.mark.integration
class TestSearchResponseFormat:
    """Test per il formato delle risposte di ricerca"""

    @pytest.fixture
    async def client(self, sample_search_results):
        """Client HTTP per test"""

        async def mock_get_components():
            components = MagicMock()
            components.retriever = AsyncMock()
            components.retriever.search = AsyncMock(return_value=sample_search_results)
            components.retriever.query_classifier = MagicMock()
            components.retriever.query_classifier.classify_query = MagicMock(
                return_value=QueryType.PROCEDURE
            )
            components.generator = AsyncMock()
            components.generator.generate_response = AsyncMock(
                return_value=RAGResponse(
                    query="test",
                    query_type=QueryType.PROCEDURE,
                    answer="Risposta procedura",
                    sources=sample_search_results,
                    confidence=0.9,
                    processing_time_ms=200,
                )
            )
            return components

        with patch(
            "src.rag_gestionale.api.routers.search.get_components", mock_get_components
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                yield client

    @pytest.mark.asyncio
    async def test_response_structure(self, client):
        """Test struttura risposta"""
        request_data = {"query": "come creare fattura", "top_k": 5}

        response = await client.post("/api/v1/search", json=request_data)

        assert response.status_code == 200
        data = response.json()

        # Verifica campi obbligatori
        assert "query" in data
        assert "query_type" in data
        assert "answer" in data
        assert "sources" in data
        assert "confidence" in data
        assert "processing_time_ms" in data

        # Verifica tipi
        assert isinstance(data["query"], str)
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["confidence"], (int, float))
        assert isinstance(data["processing_time_ms"], int)

    @pytest.mark.asyncio
    async def test_source_structure(self, client):
        """Test struttura sorgenti"""
        request_data = {"query": "test query", "top_k": 5, "include_sources": True}

        response = await client.post("/api/v1/search", json=request_data)

        assert response.status_code == 200
        data = response.json()

        sources = data["sources"]

        if sources:
            # Verifica struttura di ogni sorgente
            for source in sources:
                assert "chunk" in source
                assert "score" in source
                assert "explanation" in source

                # Verifica chunk
                chunk = source["chunk"]
                assert "content" in chunk
                assert "metadata" in chunk

                # Verifica metadata
                metadata = chunk["metadata"]
                assert "id" in metadata
                assert "title" in metadata
                assert "content_type" in metadata

    @pytest.mark.asyncio
    async def test_confidence_range(self, client):
        """Test che la confidenza sia nel range corretto"""
        request_data = {"query": "test query", "top_k": 5}

        response = await client.post("/api/v1/search", json=request_data)

        assert response.status_code == 200
        data = response.json()

        confidence = data["confidence"]
        assert 0.0 <= confidence <= 1.0

    @pytest.mark.asyncio
    async def test_query_type_values(self, client):
        """Test che il query_type sia uno dei valori validi"""
        request_data = {"query": "test query", "top_k": 5}

        response = await client.post("/api/v1/search", json=request_data)

        assert response.status_code == 200
        data = response.json()

        query_type = data["query_type"]
        valid_types = ["GENERAL", "PROCEDURE", "PARAMETER", "ERROR", "FAQ"]
        assert query_type in valid_types
