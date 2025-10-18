"""
Integration tests per gli endpoint di ingestione
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.rag_gestionale.api.main import app


@pytest.mark.integration
class TestIngestAPI:
    """Test per gli endpoint di ingestione"""

    @pytest.fixture
    async def mock_components(self, sample_chunks_list):
        """Mock dei componenti RAG"""
        components = MagicMock()

        # Mock ingestion coordinator
        components.ingestion_coordinator = AsyncMock()
        components.ingestion_coordinator.ingest_from_urls = AsyncMock(
            return_value=sample_chunks_list
        )
        components.ingestion_coordinator.ingest_from_directory = AsyncMock(
            return_value=sample_chunks_list
        )

        # Mock retriever
        components.retriever = AsyncMock()
        components.retriever.add_chunks = AsyncMock()

        return components

    @pytest.fixture
    async def client(self, mock_components):
        """Client HTTP per test"""
        with patch(
            "src.rag_gestionale.api.routers.ingest.get_components"
        ) as mock_get_components:
            mock_get_components.return_value = mock_components

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                yield client

    @pytest.mark.asyncio
    async def test_ingest_from_urls(self, client):
        """Test ingestione da URL"""
        request_data = {"urls": ["http://example.com/doc1", "http://example.com/doc2"]}

        response = await client.post("/api/v1/ingest", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "message" in data
        assert "chunks_processed" in data
        assert "processing_time_ms" in data
        assert data["status"] == "success"
        assert data["chunks_processed"] > 0

    @pytest.mark.asyncio
    async def test_ingest_from_directory(self, client):
        """Test ingestione da directory"""
        request_data = {"directory": "/path/to/docs"}

        response = await client.post("/api/v1/ingest", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["chunks_processed"] > 0

    @pytest.mark.asyncio
    async def test_ingest_urls_and_directory(self, client):
        """Test ingestione da URL e directory insieme"""
        request_data = {
            "urls": ["http://example.com/doc"],
            "directory": "/path/to/docs",
        }

        response = await client.post("/api/v1/ingest", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        # Dovrebbe processare chunks da entrambe le sorgenti
        assert data["chunks_processed"] > 0

    @pytest.mark.asyncio
    async def test_ingest_no_source(self, client):
        """Test ingestione senza specificare sorgente"""
        request_data = {}

        response = await client.post("/api/v1/ingest", json=request_data)

        # Dovrebbe ritornare errore
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_ingest_empty_urls(self, client):
        """Test ingestione con lista URL vuota"""
        request_data = {"urls": []}

        response = await client.post("/api/v1/ingest", json=request_data)

        # Dovrebbe ritornare errore
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_ingest_single_url(self, client):
        """Test ingestione singolo URL"""
        request_data = {"urls": ["http://example.com/manual.pdf"]}

        response = await client.post("/api/v1/ingest", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_ingest_error_handling(self, client, mock_components):
        """Test gestione errori durante ingestione"""
        # Mock che solleva eccezione
        mock_components.ingestion_coordinator.ingest_from_urls = AsyncMock(
            side_effect=Exception("Ingest error")
        )

        request_data = {"urls": ["http://example.com/doc"]}

        response = await client.post("/api/v1/ingest", json=request_data)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_ingest_no_chunks_produced(self, client, mock_components):
        """Test ingestione che non produce chunk"""
        # Mock che ritorna lista vuota
        mock_components.ingestion_coordinator.ingest_from_urls = AsyncMock(
            return_value=[]
        )

        request_data = {"urls": ["http://example.com/empty"]}

        response = await client.post("/api/v1/ingest", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["chunks_processed"] == 0

    @pytest.mark.asyncio
    async def test_ingest_response_format(self, client):
        """Test formato risposta ingestione"""
        request_data = {"urls": ["http://example.com/doc"]}

        response = await client.post("/api/v1/ingest", json=request_data)

        assert response.status_code == 200
        data = response.json()

        # Verifica campi obbligatori
        assert "status" in data
        assert "message" in data
        assert "chunks_processed" in data
        assert "processing_time_ms" in data

        # Verifica tipi
        assert isinstance(data["status"], str)
        assert isinstance(data["message"], str)
        assert isinstance(data["chunks_processed"], int)
        assert isinstance(data["processing_time_ms"], int)

        # Verifica valori
        assert data["status"] in ["success", "error"]
        assert data["chunks_processed"] >= 0
        assert data["processing_time_ms"] >= 0


@pytest.mark.integration
class TestIngestValidation:
    """Test per la validazione degli input di ingestione"""

    @pytest.fixture
    async def client(self):
        """Client HTTP per test"""

        async def mock_get_components():
            components = MagicMock()
            components.ingestion_coordinator = AsyncMock()
            components.ingestion_coordinator.ingest_from_urls = AsyncMock(
                return_value=[]
            )
            components.retriever = AsyncMock()
            components.retriever.add_chunks = AsyncMock()
            return components

        with patch(
            "src.rag_gestionale.api.routers.ingest.get_components", mock_get_components
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                yield client

    @pytest.mark.asyncio
    async def test_invalid_request_body(self, client):
        """Test richiesta con body invalido"""
        response = await client.post("/api/v1/ingest", json={"invalid_field": "value"})

        # Dovrebbe accettare ma ritornare errore 400
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_malformed_json(self, client):
        """Test richiesta con JSON malformato"""
        response = await client.post(
            "/api/v1/ingest",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422


@pytest.mark.integration
class TestIngestFlow:
    """Test per il flusso completo di ingestione"""

    @pytest.fixture
    async def client(self, sample_chunks_list):
        """Client HTTP per test del flusso completo"""

        async def mock_get_components():
            components = MagicMock()

            # Simula ingestion coordinator reale
            coordinator = AsyncMock()
            coordinator.ingest_from_urls = AsyncMock(return_value=sample_chunks_list)
            components.ingestion_coordinator = coordinator

            # Simula retriever che riceve i chunk
            retriever = AsyncMock()
            chunks_added = []

            async def add_chunks_side_effect(chunks):
                chunks_added.extend(chunks)

            retriever.add_chunks = AsyncMock(side_effect=add_chunks_side_effect)
            components.retriever = retriever

            return components

        with patch(
            "src.rag_gestionale.api.routers.ingest.get_components", mock_get_components
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                yield client

    @pytest.mark.asyncio
    async def test_full_ingest_flow(self, client):
        """Test flusso completo: ingest -> process -> index"""
        request_data = {"urls": ["http://example.com/manual.pdf"]}

        response = await client.post("/api/v1/ingest", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["chunks_processed"] > 0
        assert data["processing_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_ingest_multiple_urls_sequential(self, client):
        """Test ingestione multipla sequenziale"""
        urls = [
            "http://example.com/doc1",
            "http://example.com/doc2",
            "http://example.com/doc3",
        ]

        request_data = {"urls": urls}

        response = await client.post("/api/v1/ingest", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
