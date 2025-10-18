"""
Unit tests per il modulo IntelligentChunker
"""

import pytest

from src.rag_gestionale.core.models import ContentType, DocumentChunk
from src.rag_gestionale.ingest.chunker import (
    ChunkingContext,
    IntelligentChunker,
    chunk_documents,
)


@pytest.mark.unit
class TestIntelligentChunker:
    """Test per la classe IntelligentChunker"""

    @pytest.fixture
    def chunker(self):
        """Fixture che crea un'istanza di IntelligentChunker"""
        return IntelligentChunker()

    @pytest.fixture
    def chunking_context(self):
        """Fixture per il contesto di chunking"""
        return ChunkingContext(
            document_title="Test Document",
            module="TestModule",
            version="1.0",
            source_url="http://test.com/doc",
        )

    def test_chunker_initialization(self, chunker):
        """Verifica che il chunker si inizializzi correttamente"""
        assert chunker is not None
        assert chunker.settings is not None
        assert len(chunker.section_boundaries) > 0
        assert len(chunker.step_patterns) > 0

    def test_chunk_small_document(
        self, chunker, sample_document_chunk, chunking_context
    ):
        """Test chunking di un documento piccolo (dovrebbe creare un solo chunk)"""
        chunks = chunker.chunk_document(sample_document_chunk, chunking_context)

        assert len(chunks) >= 1
        assert all(isinstance(c, DocumentChunk) for c in chunks)
        assert all(c.metadata.id.startswith("test_chunk_001") for c in chunks)

    def test_chunk_procedure_document(
        self, chunker, sample_procedure_chunk, chunking_context
    ):
        """Test chunking di una procedura"""
        chunks = chunker.chunk_document(sample_procedure_chunk, chunking_context)

        assert len(chunks) >= 1
        # Verifica che almeno un chunk sia marcato come procedura o step
        content_types = [c.metadata.content_type for c in chunks]
        assert ContentType.PROCEDURE in content_types or any(
            "step" in c.metadata.id for c in chunks
        )

    def test_chunk_parameter_document(
        self, chunker, sample_parameter_chunk, chunking_context
    ):
        """Test chunking di un parametro"""
        chunks = chunker.chunk_document(sample_parameter_chunk, chunking_context)

        assert len(chunks) >= 1
        assert all(c.metadata.content_type == ContentType.PARAMETER for c in chunks)
        # I parametri dovrebbero essere atomici (no overlap)
        assert all(c.metadata.param_name == "IVA_DEFAULT" for c in chunks)

    def test_chunk_error_document(self, chunker, sample_error_chunk, chunking_context):
        """Test chunking di un errore"""
        chunks = chunker.chunk_document(sample_error_chunk, chunking_context)

        assert len(chunks) == 1  # Gli errori dovrebbero essere atomici
        assert chunks[0].metadata.content_type == ContentType.ERROR
        assert chunks[0].metadata.error_code == "ERR-001"

    def test_split_into_steps(self, chunker, sample_procedure_chunk, chunking_context):
        """Test della divisione in step procedurali"""
        content = """
        1) Primo step della procedura
        Descrizione del primo step con dettagli importanti.

        2) Secondo step della procedura
        Descrizione del secondo step con altre informazioni.

        3) Terzo step finale
        Completamento della procedura.
        """

        metadata = sample_procedure_chunk.metadata
        parent_id = "parent_chunk_001"

        steps = chunker._split_into_steps(
            content, metadata, chunking_context, parent_id
        )

        assert len(steps) >= 2  # Dovrebbe identificare almeno 2 step
        assert all("step" in chunk.metadata.id for chunk in steps)
        assert all(chunk.metadata.parent_chunk_id == parent_id for chunk in steps)

    def test_split_by_paragraphs(self, chunker):
        """Test della divisione in paragrafi"""
        content = """
        Primo paragrafo con contenuto significativo.

        Secondo paragrafo con altre informazioni importanti.


        Terzo paragrafo dopo doppio newline.

        P
        """  # Paragrafo troppo corto da filtrare

        paragraphs = chunker._split_by_paragraphs(content)

        assert len(paragraphs) >= 3
        assert all(len(p) > 20 for p in paragraphs)  # Filtro paragrafi corti
        assert "Primo paragrafo" in paragraphs[0]

    def test_create_chunk_metadata(
        self, chunker, sample_chunk_metadata, chunking_context
    ):
        """Test creazione chunk con metadati corretti"""
        chunk = chunker._create_chunk(
            content="Test content for chunk",
            chunk_type="concept",
            original_metadata=sample_chunk_metadata,
            context=chunking_context,
            chunk_index=0,
        )

        assert chunk is not None
        assert chunk.content == "Test content for chunk"
        assert chunk.metadata.id.startswith("test_chunk_001")
        assert chunk.metadata.title == sample_chunk_metadata.title
        assert chunk.metadata.hash is not None

    def test_create_chunk_with_parent(
        self, chunker, sample_chunk_metadata, chunking_context
    ):
        """Test creazione chunk figlio con parent_id"""
        parent_id = "parent_chunk_001"

        chunk = chunker._create_chunk(
            content="Child content",
            chunk_type="step",
            original_metadata=sample_chunk_metadata,
            context=chunking_context,
            chunk_index=1,
            parent_id=parent_id,
        )

        assert chunk.metadata.parent_chunk_id == parent_id
        assert "child" in chunk.metadata.id

    def test_add_overlap_single_chunk(self, chunker, sample_chunks_list):
        """Test che l'overlap non venga aggiunto se c'è un solo chunk"""
        single_chunk = [sample_chunks_list[0]]
        context = ChunkingContext(
            document_title="Test",
            module="Test",
            version="1.0",
            source_url="http://test.com",
        )

        result = chunker._add_overlap_and_finalize(single_chunk, context)

        assert len(result) == 1
        assert result[0].content == single_chunk[0].content

    def test_get_overlap_tokens(self, chunker):
        """Test calcolo token di overlap per tipo di contenuto"""
        proc_overlap = chunker._get_overlap_tokens(ContentType.PROCEDURE)
        param_overlap = chunker._get_overlap_tokens(ContentType.PARAMETER)
        concept_overlap = chunker._get_overlap_tokens(ContentType.CONCEPT)

        assert proc_overlap > 0
        assert param_overlap >= 0
        assert concept_overlap > 0
        # I parametri dovrebbero avere overlap minore
        assert param_overlap <= proc_overlap

    def test_chunk_adaptive_small(
        self, chunker, sample_document_chunk, chunking_context
    ):
        """Test chunking adattivo per contenuto piccolo"""
        # Chunk piccolo dovrebbe restare intero
        chunks = chunker._chunk_adaptive(sample_document_chunk, chunking_context)

        assert len(chunks) == 1
        assert chunks[0].metadata.content_type == ContentType.CONCEPT

    def test_create_summary_for_parent(self, chunker):
        """Test creazione summary estrattivo per chunk parent"""
        long_content = """
        Prima frase importante del documento.
        Seconda frase con informazioni chiave.
        Terza frase con dettagli aggiuntivi.
        Quarta frase intermedia.
        Quinta frase intermedia.
        Ultima frase conclusiva del documento.
        """

        summary = chunker._create_summary_for_parent(long_content)

        assert len(summary) > 0
        assert "Prima frase" in summary
        # Dovrebbe contenere prime frasi e possibilmente ultima


@pytest.mark.unit
def test_chunk_documents_utility(sample_chunks_list):
    """Test della funzione utility chunk_documents"""
    result = chunk_documents(sample_chunks_list)

    assert len(result) >= len(sample_chunks_list)
    assert all(isinstance(c, DocumentChunk) for c in result)


@pytest.mark.unit
class TestChunkingContext:
    """Test per ChunkingContext"""

    def test_context_creation(self):
        """Test creazione contesto di chunking"""
        context = ChunkingContext(
            document_title="Test Doc",
            module="TestModule",
            version="1.0",
            source_url="http://test.com",
        )

        assert context.document_title == "Test Doc"
        assert context.module == "TestModule"
        assert context.version == "1.0"
        assert context.source_url == "http://test.com"
        assert context.total_chunks == 0
        assert context.parent_chunk_id is None

    def test_context_with_parent(self):
        """Test creazione contesto con parent chunk"""
        context = ChunkingContext(
            document_title="Test",
            module="Test",
            version="1.0",
            source_url="http://test.com",
            parent_chunk_id="parent_001",
        )

        assert context.parent_chunk_id == "parent_001"
