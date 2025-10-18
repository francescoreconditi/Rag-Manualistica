"""
Unit tests per il modulo VectorStore
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag_gestionale.core.models import DocumentChunk, SearchResult
from src.rag_gestionale.retrieval.vector_store import VectorStore


@pytest.mark.unit
@pytest.mark.requires_qdrant
class TestVectorStore:
    """Test per la classe VectorStore"""

    @pytest.fixture
    async def vector_store(self, mock_qdrant_client, mock_sentence_transformer):
        """Fixture che crea un'istanza di VectorStore con mock"""
        with (
            patch(
                "src.rag_gestionale.retrieval.vector_store.QdrantClient"
            ) as mock_sync_client,
            patch(
                "src.rag_gestionale.retrieval.vector_store.AsyncQdrantClient"
            ) as mock_async_client,
            patch(
                "src.rag_gestionale.retrieval.vector_store.SentenceTransformer"
            ) as mock_st,
        ):
            mock_async_client.return_value = mock_qdrant_client
            mock_sync_client.return_value = MagicMock()
            mock_st.return_value = mock_sentence_transformer

            store = VectorStore()
            await store.initialize()
            yield store
            await store.close()

    @pytest.mark.asyncio
    async def test_initialization(self, vector_store):
        """Verifica che il vector store si inizializzi correttamente"""
        assert vector_store is not None
        assert vector_store.client is not None
        assert vector_store.async_client is not None
        assert vector_store.embedding_model is not None
        assert vector_store.collection_name is not None

    @pytest.mark.asyncio
    async def test_add_chunks(self, vector_store, sample_chunks_list):
        """Test aggiunta chunk al vector store"""
        await vector_store.add_chunks(sample_chunks_list)

        # Verifica che upsert sia stato chiamato
        assert vector_store.async_client.upsert.called

    @pytest.mark.asyncio
    async def test_add_empty_chunks(self, vector_store):
        """Test aggiunta lista vuota di chunk"""
        await vector_store.add_chunks([])

        # Non dovrebbe chiamare upsert
        assert not vector_store.async_client.upsert.called

    @pytest.mark.asyncio
    async def test_search(self, vector_store):
        """Test ricerca nel vector store"""
        query = "come creare una fattura"

        results = await vector_store.search(query, top_k=5)

        assert isinstance(results, list)
        # Con il mock dovrebbe ritornare lista vuota
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_with_filters(self, vector_store):
        """Test ricerca con filtri sui metadati"""
        query = "parametro IVA"
        filters = {"module": "Contabilità", "version": "1.0"}

        results = await vector_store.search(query, top_k=10, filters=filters)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_score_threshold(self, vector_store):
        """Test ricerca con soglia di score minimo"""
        query = "test query"
        score_threshold = 0.7

        results = await vector_store.search(
            query, top_k=10, score_threshold=score_threshold
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_delete_chunks_by_url(
        self, vector_store, mock_qdrant_client, sample_document_chunk
    ):
        """Test eliminazione chunk per URL"""
        source_url = "http://test.com/doc"

        # Mock del count per ritornare 5 chunk da eliminare
        mock_qdrant_client.count.return_value = MagicMock(count=5)

        deleted = await vector_store.delete_chunks_by_url(source_url)

        assert deleted == 5
        assert mock_qdrant_client.delete.called

    @pytest.mark.asyncio
    async def test_delete_chunks_by_url_not_found(
        self, vector_store, mock_qdrant_client
    ):
        """Test eliminazione chunk per URL non esistente"""
        source_url = "http://notfound.com/doc"

        # Mock del count per ritornare 0
        mock_qdrant_client.count.return_value = MagicMock(count=0)

        deleted = await vector_store.delete_chunks_by_url(source_url)

        assert deleted == 0

    @pytest.mark.asyncio
    async def test_get_chunk_by_id(self, vector_store, mock_qdrant_client):
        """Test recupero chunk per ID"""
        chunk_id = "test_chunk_001"

        # Mock retrieve senza risultati
        mock_qdrant_client.retrieve.return_value = []

        chunk = await vector_store.get_chunk_by_id(chunk_id)

        assert chunk is None

    @pytest.mark.asyncio
    async def test_delete_chunk(self, vector_store, mock_qdrant_client):
        """Test eliminazione singolo chunk"""
        chunk_id = "test_chunk_001"

        success = await vector_store.delete_chunk(chunk_id)

        assert success is True
        assert mock_qdrant_client.delete.called

    @pytest.mark.asyncio
    async def test_update_chunk(self, vector_store, sample_document_chunk):
        """Test aggiornamento chunk esistente"""
        success = await vector_store.update_chunk(sample_document_chunk)

        assert success is True

    @pytest.mark.asyncio
    async def test_get_collection_stats(self, vector_store, mock_qdrant_client):
        """Test recupero statistiche collection"""
        # Mock info collection
        mock_info = MagicMock()
        mock_info.points_count = 100
        mock_info.config.params.vectors.size = 384
        mock_info.config.params.vectors.distance = "Cosine"
        mock_info.status = "green"
        mock_qdrant_client.get_collection.return_value = mock_info

        stats = await vector_store.get_collection_stats()

        assert stats["total_points"] == 100
        assert stats["vector_size"] == 384

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, vector_store):
        """Test generazione embeddings in batch"""
        texts = ["testo uno", "testo due", "testo tre"]

        embeddings = await vector_store._generate_embeddings_batch(texts)

        assert embeddings is not None
        # Il mock ritorna un singolo vettore, ma nella realtà ne ritornerebbe 3

    @pytest.mark.asyncio
    async def test_generate_embedding_single(self, vector_store):
        """Test generazione embedding per singolo testo"""
        text = "singolo testo di test"

        embedding = await vector_store._generate_embedding(text)

        assert embedding is not None

    def test_chunk_to_payload(self, vector_store, sample_document_chunk):
        """Test conversione chunk in payload Qdrant"""
        payload = vector_store._chunk_to_payload(sample_document_chunk)

        assert payload is not None
        assert "chunk_id" in payload
        assert "title" in payload
        assert "content" in payload
        assert "content_type" in payload
        assert payload["chunk_id"] == sample_document_chunk.metadata.id
        assert payload["title"] == sample_document_chunk.metadata.title

    def test_chunk_to_payload_with_optional_fields(
        self, vector_store, sample_parameter_chunk
    ):
        """Test conversione chunk con campi opzionali"""
        payload = vector_store._chunk_to_payload(sample_parameter_chunk)

        assert "param_name" in payload
        assert payload["param_name"] == "IVA_DEFAULT"

    def test_payload_to_chunk(self, vector_store, sample_document_chunk):
        """Test conversione payload Qdrant in chunk"""
        # Prima converte in payload
        payload = vector_store._chunk_to_payload(sample_document_chunk)

        # Poi riconverte in chunk
        reconstructed_chunk = vector_store._payload_to_chunk(payload)

        assert reconstructed_chunk is not None
        assert isinstance(reconstructed_chunk, DocumentChunk)
        assert reconstructed_chunk.metadata.id == sample_document_chunk.metadata.id
        assert (
            reconstructed_chunk.metadata.title == sample_document_chunk.metadata.title
        )
        assert (
            reconstructed_chunk.metadata.content_type
            == sample_document_chunk.metadata.content_type
        )

    def test_build_filter_module(self, vector_store):
        """Test costruzione filtro per modulo"""
        filters = {"module": "Fatturazione"}

        qdrant_filter = vector_store._build_filter(filters)

        assert qdrant_filter is not None
        assert len(qdrant_filter.must) == 1

    def test_build_filter_multiple(self, vector_store):
        """Test costruzione filtro multiplo"""
        filters = {
            "module": "Contabilità",
            "version": "1.0",
            "content_type": "PARAMETER",
        }

        qdrant_filter = vector_store._build_filter(filters)

        assert qdrant_filter is not None
        assert len(qdrant_filter.must) == 3

    def test_build_filter_section_level_range(self, vector_store):
        """Test costruzione filtro con range per section_level"""
        filters = {"section_level": {"min": 1, "max": 3}}

        qdrant_filter = vector_store._build_filter(filters)

        assert qdrant_filter is not None
        assert len(qdrant_filter.must) == 1

    def test_build_filter_empty(self, vector_store):
        """Test costruzione filtro vuoto"""
        filters = {}

        qdrant_filter = vector_store._build_filter(filters)

        assert qdrant_filter is None

    @pytest.mark.asyncio
    async def test_ensure_collection_exists_already_exists(
        self, vector_store, mock_qdrant_client
    ):
        """Test creazione collection quando già esiste"""
        # Mock collection esistente
        mock_qdrant_client.get_collection.return_value = MagicMock()

        await vector_store._ensure_collection_exists()

        # Non dovrebbe chiamare create_collection
        assert not mock_qdrant_client.create_collection.called

    @pytest.mark.asyncio
    async def test_ensure_collection_exists_create_new(
        self, vector_store, mock_qdrant_client
    ):
        """Test creazione nuova collection"""
        # Mock collection non esistente
        mock_qdrant_client.get_collection.side_effect = Exception("Not found")

        await vector_store._ensure_collection_exists()

        # Dovrebbe chiamare create_collection
        assert mock_qdrant_client.create_collection.called


@pytest.mark.unit
class TestVectorStoreIntegration:
    """Test di integrazione per VectorStore (senza mock esterni)"""

    @pytest.mark.asyncio
    async def test_chunk_roundtrip(self, sample_document_chunk):
        """Test roundtrip: chunk -> payload -> chunk"""
        store = VectorStore()

        # Converti in payload
        payload = store._chunk_to_payload(sample_document_chunk)

        # Riconverti in chunk
        reconstructed = store._payload_to_chunk(payload)

        # Verifica che i dati siano preservati
        assert reconstructed.content == sample_document_chunk.content
        assert reconstructed.metadata.id == sample_document_chunk.metadata.id
        assert reconstructed.metadata.title == sample_document_chunk.metadata.title
        assert (
            reconstructed.metadata.content_type
            == sample_document_chunk.metadata.content_type
        )
        assert reconstructed.metadata.module == sample_document_chunk.metadata.module
        assert reconstructed.metadata.version == sample_document_chunk.metadata.version
