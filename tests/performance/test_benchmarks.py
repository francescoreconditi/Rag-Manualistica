"""
Benchmark tests per componenti critici del sistema

Richiede pytest-benchmark:
    uv pip install pytest-benchmark

Esecuzione:
    uv run pytest tests/performance/ --benchmark-only
"""

import pytest

pytestmark = pytest.mark.slow


@pytest.mark.benchmark
class TestChunkerBenchmark:
    """Benchmark per IntelligentChunker"""

    @pytest.fixture
    def large_document(self, sample_document_chunk):
        """Crea un documento grande per benchmark"""
        # Duplica il contenuto per creare un documento più grande
        content = sample_document_chunk.content * 100
        large_chunk = sample_document_chunk
        large_chunk.content = content
        return large_chunk

    def test_chunk_large_document_benchmark(
        self, benchmark, large_document, sample_chunk_metadata
    ):
        """Benchmark chunking documento grande"""
        from src.rag_gestionale.ingest.chunker import (
            ChunkingContext,
            IntelligentChunker,
        )

        chunker = IntelligentChunker()
        context = ChunkingContext(
            document_title="Test",
            module="Test",
            version="1.0",
            source_url="http://test.com",
        )

        # Benchmark
        result = benchmark(chunker.chunk_document, large_document, context)

        assert len(result) > 0

    def test_split_by_paragraphs_benchmark(self, benchmark):
        """Benchmark divisione paragrafi"""
        from src.rag_gestionale.ingest.chunker import IntelligentChunker

        chunker = IntelligentChunker()

        # Testo con molti paragrafi
        content = "\n\n".join([f"Paragrafo {i} con contenuto" for i in range(1000)])

        result = benchmark(chunker._split_by_paragraphs, content)

        assert len(result) > 0


@pytest.mark.benchmark
class TestVectorStoreBenchmark:
    """Benchmark per VectorStore (con mock)"""

    @pytest.fixture
    def mock_embedding_model(self):
        """Mock veloce del modello"""
        from unittest.mock import MagicMock
        import numpy as np

        model = MagicMock()
        model.encode = MagicMock(
            side_effect=lambda texts, **kwargs: np.random.rand(len(texts), 384)
        )
        return model

    def test_generate_embeddings_batch_benchmark(
        self, benchmark, sample_chunks_list, mock_embedding_model
    ):
        """Benchmark generazione embeddings batch"""
        import asyncio
        from src.rag_gestionale.retrieval.vector_store import VectorStore

        store = VectorStore()
        store.embedding_model = mock_embedding_model

        texts = [chunk.content for chunk in sample_chunks_list] * 10  # 40 testi

        # Benchmark (wrapper sincrono per asyncio)
        def run_async():
            return asyncio.run(store._generate_embeddings_batch(texts))

        result = benchmark(run_async)

        assert len(result) > 0


@pytest.mark.benchmark
class TestRetrieverBenchmark:
    """Benchmark per HybridRetriever"""

    def test_combine_results_benchmark(self, benchmark, sample_search_results):
        """Benchmark combinazione risultati"""
        from src.rag_gestionale.retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever()

        # Duplica risultati per test più significativo
        vector_results = sample_search_results * 5
        lexical_results = sample_search_results * 5

        result = benchmark(retriever._combine_results, vector_results, lexical_results)

        assert len(result) > 0

    def test_diversify_results_benchmark(self, benchmark, sample_search_results):
        """Benchmark diversificazione risultati"""
        from src.rag_gestionale.retrieval.hybrid_retriever import HybridRetriever

        retriever = HybridRetriever()

        # Molti risultati per test
        results = sample_search_results * 20

        result = benchmark(retriever._diversify_results, results)

        assert len(result) > 0


@pytest.mark.benchmark
class TestGeneratorBenchmark:
    """Benchmark per ResponseGenerator"""

    def test_filter_quality_results_benchmark(self, benchmark, sample_search_results):
        """Benchmark filtro qualità"""
        from src.rag_gestionale.generation.generator import ResponseGenerator

        generator = ResponseGenerator()

        # Molti risultati
        results = sample_search_results * 10

        result = benchmark(generator._filter_quality_results, results)

        assert len(result) >= 0

    def test_calculate_confidence_benchmark(self, benchmark, sample_search_results):
        """Benchmark calcolo confidenza"""
        from src.rag_gestionale.generation.generator import ResponseGenerator

        generator = ResponseGenerator()

        response_text = "Risposta di test con contenuto. " * 50

        result = benchmark(
            generator._calculate_confidence, sample_search_results, response_text
        )

        assert 0.0 <= result <= 1.0


@pytest.mark.benchmark
class TestParserBenchmark:
    """Benchmark per parser"""

    def test_pdf_text_cleaning_benchmark(self, benchmark):
        """Benchmark pulizia testo PDF"""
        from src.rag_gestionale.ingest.pdf_parser import PDFParser

        parser = PDFParser()

        # Testo sporco con molti problemi
        dirty_text = (
            """
        Testo normale
        123
        Una riga valida
        45

        Altra riga
        """
            * 100
        )

        result = benchmark(parser._clean_pdf_text, dirty_text)

        assert len(result) > 0

    def test_html_simple_parse_benchmark(self, benchmark):
        """Benchmark parsing HTML semplice"""
        from src.rag_gestionale.ingest.html_parser import HTMLParser

        parser = HTMLParser()

        html = "<html><body><h1>Title</h1><p>Content</p></body></html>" * 50

        result = benchmark(parser._simple_parse, "http://test.com", html)

        sections, metadata = result
        assert len(sections) > 0


# Utility per comparare performance
@pytest.mark.benchmark
class TestPerformanceComparison:
    """Confronto performance tra approcci diversi"""

    def test_compare_text_normalization(self, benchmark):
        """Confronto approcci normalizzazione testo"""
        from src.rag_gestionale.core.utils import normalize_text

        text = "  Testo    con    spazi   multipli   " * 100

        result = benchmark(normalize_text, text)

        assert len(result) > 0


# Note per benchmark:
# - Eseguire con: pytest tests/performance/ --benchmark-only
# - Comparare risultati: pytest tests/performance/ --benchmark-compare
# - Salvare baseline: pytest tests/performance/ --benchmark-save=baseline
# - Confrontare con baseline: pytest tests/performance/ --benchmark-compare=baseline
