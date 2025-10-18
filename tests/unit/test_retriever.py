"""
Unit tests per il modulo HybridRetriever
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag_gestionale.core.models import QueryType, SearchResult
from src.rag_gestionale.retrieval.hybrid_retriever import (
    HybridRetriever,
    QueryClassifier,
)


@pytest.mark.unit
class TestQueryClassifier:
    """Test per QueryClassifier"""

    @pytest.fixture
    def classifier(self):
        """Fixture che crea un classificatore"""
        return QueryClassifier()

    def test_classify_error_query(self, classifier):
        """Test classificazione query errore"""
        queries = [
            "errore ERR-001",
            "codice errore fatturazione",
            "warning WRN-123",
            "non funziona la stampa",
        ]

        for query in queries:
            result = classifier.classify_query(query)
            assert result == QueryType.ERROR, f"Failed for query: {query}"

    def test_classify_parameter_query(self, classifier):
        """Test classificazione query parametro"""
        queries = [
            "come impostare il parametro IVA",
            "dove trovo l'impostazione del magazzino",
            "valori ammessi per il campo",
            "parametro predefinito fattura",
        ]

        for query in queries:
            result = classifier.classify_query(query)
            assert result == QueryType.PARAMETER, f"Failed for query: {query}"

    def test_classify_procedure_query(self, classifier):
        """Test classificazione query procedura"""
        queries = [
            "come creare una fattura",
            "procedura per eseguire la chiusura",
            "step per configurare il sistema",
            "come fare per stampare",
        ]

        for query in queries:
            result = classifier.classify_query(query)
            assert result == QueryType.PROCEDURE, f"Failed for query: {query}"

    def test_classify_general_query(self, classifier):
        """Test classificazione query generica"""
        queries = [
            "informazioni sul modulo contabilità",
            "cos'è il gestionale",
            "caratteristiche principali",
        ]

        for query in queries:
            result = classifier.classify_query(query)
            assert result == QueryType.GENERAL, f"Failed for query: {query}"


@pytest.mark.unit
@pytest.mark.requires_qdrant
@pytest.mark.requires_opensearch
class TestHybridRetriever:
    """Test per HybridRetriever"""

    @pytest.fixture
    async def mock_vector_store(self, sample_search_results):
        """Mock del VectorStore"""
        store = AsyncMock()
        store.initialize = AsyncMock()
        store.search = AsyncMock(return_value=sample_search_results[:2])
        store.add_chunks = AsyncMock()
        store.delete_chunks_by_url = AsyncMock(return_value=5)
        store.get_chunk_by_id = AsyncMock(return_value=None)
        store.delete_chunk = AsyncMock(return_value=True)
        store.get_collection_stats = AsyncMock(
            return_value={"total_points": 100, "vector_size": 384}
        )
        store.close = AsyncMock()
        return store

    @pytest.fixture
    async def mock_lexical_search(self, sample_search_results):
        """Mock del LexicalSearch"""
        search = AsyncMock()
        search.initialize = AsyncMock()
        search.search = AsyncMock(return_value=sample_search_results[1:3])
        search.add_chunks = AsyncMock()
        search.delete_chunks_by_url = AsyncMock(return_value=5)
        search.get_chunk_by_id = AsyncMock(return_value=None)
        search.delete_chunk = AsyncMock(return_value=True)
        search.get_index_stats = AsyncMock(
            return_value={"total_docs": 100, "index_size": "10MB"}
        )
        search.close = AsyncMock()
        return search

    @pytest.fixture
    async def retriever(
        self, mock_vector_store, mock_lexical_search, mock_cross_encoder
    ):
        """Fixture che crea un HybridRetriever con mock"""
        with (
            patch(
                "src.rag_gestionale.retrieval.hybrid_retriever.VectorStore"
            ) as mock_vs,
            patch(
                "src.rag_gestionale.retrieval.hybrid_retriever.LexicalSearch"
            ) as mock_ls,
            patch(
                "src.rag_gestionale.retrieval.hybrid_retriever.CrossEncoder"
            ) as mock_ce,
        ):
            mock_vs.return_value = mock_vector_store
            mock_ls.return_value = mock_lexical_search
            mock_ce.return_value = mock_cross_encoder

            retriever = HybridRetriever()
            await retriever.initialize()
            yield retriever
            await retriever.close()

    @pytest.mark.asyncio
    async def test_initialization(self, retriever):
        """Test inizializzazione retriever"""
        assert retriever is not None
        assert retriever.vector_store is not None
        assert retriever.lexical_search is not None
        assert retriever.query_classifier is not None
        assert retriever.reranker is not None

    @pytest.mark.asyncio
    async def test_search_basic(self, retriever):
        """Test ricerca base"""
        query = "come creare una fattura"

        results = await retriever.search(query, top_k=5)

        assert isinstance(results, list)
        assert len(results) <= 5
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_with_filters(self, retriever):
        """Test ricerca con filtri"""
        query = "parametro IVA"
        filters = {"module": "Contabilità"}

        results = await retriever.search(query, top_k=10, filters=filters)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_query_type(self, retriever):
        """Test ricerca con tipo query specificato"""
        query = "errore ERR-001"

        results = await retriever.search(query, top_k=5, query_type=QueryType.ERROR)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_auto_classification(self, retriever):
        """Test classificazione automatica query"""
        query = "come configurare il parametro"

        # Non specifichiamo query_type, dovrebbe classificarlo automaticamente
        results = await retriever.search(query, top_k=5)

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_add_chunks(self, retriever, sample_chunks_list):
        """Test aggiunta chunk al retriever"""
        await retriever.add_chunks(sample_chunks_list)

        # Verifica che entrambi i sistemi siano stati chiamati
        assert retriever.vector_store.add_chunks.called
        assert retriever.lexical_search.add_chunks.called

    @pytest.mark.asyncio
    async def test_delete_chunks_by_url(self, retriever):
        """Test eliminazione chunk per URL"""
        url = "http://test.com/doc"

        vector_deleted, lexical_deleted = await retriever.delete_chunks_by_url(url)

        assert vector_deleted == 5
        assert lexical_deleted == 5

    @pytest.mark.asyncio
    async def test_get_chunk_by_id(self, retriever):
        """Test recupero chunk per ID"""
        chunk_id = "test_001"

        chunk = await retriever.get_chunk_by_id(chunk_id)

        # Con i mock dovrebbe ritornare None
        assert chunk is None

    @pytest.mark.asyncio
    async def test_delete_chunk(self, retriever):
        """Test eliminazione singolo chunk"""
        chunk_id = "test_001"

        success = await retriever.delete_chunk(chunk_id)

        assert success is True

    @pytest.mark.asyncio
    async def test_get_stats(self, retriever):
        """Test recupero statistiche"""
        stats = await retriever.get_stats()

        assert "vector_store" in stats
        assert "lexical_search" in stats
        assert "retrieval_config" in stats

    def test_get_k_values_error(self, retriever):
        """Test calcolo k per query errore"""
        k_dense, k_lexical = retriever._get_k_values(QueryType.ERROR)

        # Per errori dovrebbe favorire lexical
        assert k_lexical > k_dense

    def test_get_k_values_parameter(self, retriever):
        """Test calcolo k per query parametro"""
        k_dense, k_lexical = retriever._get_k_values(QueryType.PARAMETER)

        # Dovrebbe essere bilanciato con leggera preferenza lexical
        assert k_lexical >= k_dense

    def test_get_k_values_procedure(self, retriever):
        """Test calcolo k per query procedura"""
        k_dense, k_lexical = retriever._get_k_values(QueryType.PROCEDURE)

        # Per procedure dovrebbe favorire semantic
        assert k_dense >= k_lexical

    def test_get_k_values_general(self, retriever):
        """Test calcolo k per query generale"""
        k_dense, k_lexical = retriever._get_k_values(QueryType.GENERAL)

        # Valori di default
        assert k_dense > 0
        assert k_lexical > 0

    def test_get_boost_params_error(self, retriever):
        """Test boost per query errore"""
        boosts = retriever._get_boost_params(QueryType.ERROR)

        assert "error_code" in boosts
        assert boosts["error_code"] > 1.0

    def test_get_boost_params_parameter(self, retriever):
        """Test boost per query parametro"""
        boosts = retriever._get_boost_params(QueryType.PARAMETER)

        assert "param_name" in boosts
        assert boosts["param_name"] > 1.0

    def test_get_boost_params_procedure(self, retriever):
        """Test boost per query procedura"""
        boosts = retriever._get_boost_params(QueryType.PROCEDURE)

        assert "title" in boosts
        assert boosts["title"] > 1.0

    def test_combine_results(self, retriever, sample_search_results):
        """Test combinazione risultati vector e lexical"""
        vector_results = sample_search_results[:2]
        lexical_results = sample_search_results[1:3]

        combined = retriever._combine_results(vector_results, lexical_results)

        assert len(combined) >= 2
        # Dovrebbe contenere risultati da entrambe le sorgenti
        assert all(isinstance(r, SearchResult) for r in combined)
        # I risultati dovrebbero essere ordinati per score
        for i in range(len(combined) - 1):
            assert combined[i].score >= combined[i + 1].score

    def test_combine_results_deduplication(self, retriever, sample_search_results):
        """Test deduplicazione nella combinazione risultati"""
        # Stesso risultato in entrambe le liste
        same_result = sample_search_results[0]
        vector_results = [same_result]
        lexical_results = [same_result]

        combined = retriever._combine_results(vector_results, lexical_results)

        # Dovrebbe contenere solo un risultato (deduplicato)
        assert len(combined) == 1

    @pytest.mark.asyncio
    async def test_rerank_results(self, retriever, sample_search_results):
        """Test reranking con cross-encoder"""
        query = "test query"

        reranked = await retriever._rerank_results(query, sample_search_results)

        assert len(reranked) == len(sample_search_results)
        # Dovrebbe aver aggiornato gli score
        assert all("Reranked" in r.explanation for r in reranked)

    @pytest.mark.asyncio
    async def test_rerank_empty_results(self, retriever):
        """Test reranking con lista vuota"""
        query = "test query"
        results = []

        reranked = await retriever._rerank_results(query, results)

        assert len(reranked) == 0

    def test_diversify_results(self, retriever, sample_search_results):
        """Test diversificazione risultati"""
        # Tutti i risultati dalla stessa sezione
        for result in sample_search_results:
            result.chunk.metadata.section_path = "same/section"

        diversified = retriever._diversify_results(sample_search_results)

        # Dovrebbe limitare risultati dalla stessa sezione
        assert len(diversified) <= len(sample_search_results)

    def test_diversify_results_different_sections(
        self, retriever, sample_search_results
    ):
        """Test diversificazione con sezioni diverse"""
        # Assegna sezioni diverse
        for i, result in enumerate(sample_search_results):
            result.chunk.metadata.section_path = f"section/{i}"

        diversified = retriever._diversify_results(sample_search_results)

        # Tutti i risultati dovrebbero essere mantenuti
        assert len(diversified) == len(sample_search_results)

    @pytest.mark.asyncio
    async def test_get_candidates(self, retriever):
        """Test ottenimento candidati da entrambi i sistemi"""
        query = "test query"
        filters = {}
        query_type = QueryType.GENERAL

        vector_results, lexical_results = await retriever._get_candidates(
            query, filters, query_type
        )

        assert isinstance(vector_results, list)
        assert isinstance(lexical_results, list)
