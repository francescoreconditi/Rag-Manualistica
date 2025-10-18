"""
Configurazione pytest e fixtures globali per tutti i test
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.rag_gestionale.core.models import (
    ChunkMetadata,
    ContentType,
    DocumentChunk,
    QueryType,
    SearchResult,
    SourceFormat,
)


# Fixtures per configurazione ambiente test
@pytest.fixture(scope="session")
def test_env():
    """Configura variabili d'ambiente per i test"""
    os.environ["TESTING"] = "true"
    os.environ["QDRANT_HOST"] = "localhost"
    os.environ["QDRANT_PORT"] = "6333"
    os.environ["OPENSEARCH_HOST"] = "localhost"
    os.environ["OPENSEARCH_PORT"] = "9200"
    os.environ["LLM_ENABLED"] = "false"
    os.environ["LLM_API_KEY"] = "test-key"


@pytest.fixture(scope="session")
def event_loop():
    """Crea event loop per test asincroni"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Fixtures per dati di test
@pytest.fixture
def sample_chunk_metadata() -> ChunkMetadata:
    """Crea metadata di esempio per un chunk"""
    return ChunkMetadata(
        id="test_chunk_001",
        title="Test Chunk Title",
        breadcrumbs=["Home", "Docs", "Section"],
        section_level=2,
        section_path="home/docs/section",
        content_type=ContentType.CONCEPT,
        version="1.0",
        module="TestModule",
        param_name=None,
        ui_path=None,
        error_code=None,
        source_url="http://test.com/doc",
        source_format=SourceFormat.HTML,
        page_range=None,
        anchor="section-1",
        lang="it",
        hash="abc123",
        updated_at=datetime.now(),
        parent_chunk_id=None,
        child_chunk_ids=[],
        image_ids=[],
    )


@pytest.fixture
def sample_document_chunk(sample_chunk_metadata) -> DocumentChunk:
    """Crea un documento chunk di esempio"""
    return DocumentChunk(
        content="Questo è un contenuto di test per il documento chunk. Contiene informazioni utili per testare il sistema.",
        metadata=sample_chunk_metadata,
    )


@pytest.fixture
def sample_procedure_chunk() -> DocumentChunk:
    """Crea un chunk di tipo procedura"""
    metadata = ChunkMetadata(
        id="proc_001",
        title="Procedura Fatturazione",
        breadcrumbs=["Fatturazione", "Guide"],
        section_level=1,
        section_path="fatturazione/guide",
        content_type=ContentType.PROCEDURE,
        version="2.0",
        module="Fatturazione",
        source_url="http://test.com/proc",
        source_format=SourceFormat.HTML,
        lang="it",
        hash="proc123",
        updated_at=datetime.now(),
    )
    content = """
    Procedura per creare una nuova fattura:

    1) Accedere al menu Fatturazione
    2) Cliccare su "Nuova Fattura"
    3) Inserire i dati del cliente
    4) Aggiungere le righe fattura
    5) Salvare e stampare
    """
    return DocumentChunk(content=content, metadata=metadata)


@pytest.fixture
def sample_parameter_chunk() -> DocumentChunk:
    """Crea un chunk di tipo parametro"""
    metadata = ChunkMetadata(
        id="param_001",
        title="Parametro IVA",
        breadcrumbs=["Configurazione", "Parametri"],
        section_level=2,
        section_path="config/params",
        content_type=ContentType.PARAMETER,
        version="1.0",
        module="Contabilità",
        param_name="IVA_DEFAULT",
        source_url="http://test.com/param",
        source_format=SourceFormat.HTML,
        lang="it",
        hash="param123",
        updated_at=datetime.now(),
    )
    content = """
    Parametro: IVA_DEFAULT

    Descrizione: Aliquota IVA predefinita per le fatture
    Valori ammessi: 0, 4, 10, 22
    Valore di default: 22
    """
    return DocumentChunk(content=content, metadata=metadata)


@pytest.fixture
def sample_error_chunk() -> DocumentChunk:
    """Crea un chunk di tipo errore"""
    metadata = ChunkMetadata(
        id="err_001",
        title="Errore ERR-001",
        breadcrumbs=["Errori", "Sistema"],
        section_level=1,
        section_path="errors/system",
        content_type=ContentType.ERROR,
        version="1.0",
        module="Sistema",
        error_code="ERR-001",
        source_url="http://test.com/err",
        source_format=SourceFormat.HTML,
        lang="it",
        hash="err123",
        updated_at=datetime.now(),
    )
    content = """
    Errore ERR-001: Connessione al database fallita

    Causa: Il sistema non riesce a connettersi al database
    Soluzione: Verificare la connessione di rete e le credenziali
    """
    return DocumentChunk(content=content, metadata=metadata)


@pytest.fixture
def sample_chunks_list(
    sample_document_chunk,
    sample_procedure_chunk,
    sample_parameter_chunk,
    sample_error_chunk,
) -> List[DocumentChunk]:
    """Lista di chunk di esempio di vari tipi"""
    return [
        sample_document_chunk,
        sample_procedure_chunk,
        sample_parameter_chunk,
        sample_error_chunk,
    ]


@pytest.fixture
def sample_search_result(sample_document_chunk) -> SearchResult:
    """Crea un risultato di ricerca di esempio"""
    return SearchResult(
        chunk=sample_document_chunk,
        score=0.85,
        explanation="Vector similarity: 0.850",
        images=[],
    )


@pytest.fixture
def sample_search_results(sample_chunks_list) -> List[SearchResult]:
    """Lista di risultati di ricerca di esempio"""
    return [
        SearchResult(
            chunk=chunk,
            score=0.9 - i * 0.1,
            explanation=f"Hybrid: {0.9 - i * 0.1:.3f}",
            images=[],
        )
        for i, chunk in enumerate(sample_chunks_list)
    ]


# Mock fixtures per servizi esterni
@pytest.fixture
def mock_qdrant_client():
    """Mock del client Qdrant"""
    client = AsyncMock()
    client.get_collection = AsyncMock(return_value=MagicMock(points_count=100))
    client.create_collection = AsyncMock()
    client.upsert = AsyncMock()
    client.search = AsyncMock(return_value=[])
    client.delete = AsyncMock()
    client.retrieve = AsyncMock(return_value=[])
    client.count = AsyncMock(return_value=MagicMock(count=0))
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_opensearch_client():
    """Mock del client OpenSearch"""
    client = AsyncMock()
    client.indices = MagicMock()
    client.indices.exists = AsyncMock(return_value=True)
    client.indices.create = AsyncMock()
    client.bulk = AsyncMock(return_value={"errors": False})
    client.search = AsyncMock(return_value={"hits": {"hits": []}})
    client.delete_by_query = AsyncMock(return_value={"deleted": 0})
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_sentence_transformer():
    """Mock del modello SentenceTransformer"""
    import numpy as np

    model = MagicMock()
    model.encode = MagicMock(return_value=np.random.rand(384))  # Mock embedding 384-dim
    model.get_sentence_embedding_dimension = MagicMock(return_value=384)
    model.device = MagicMock()
    model.device.type = "cpu"
    return model


@pytest.fixture
def mock_cross_encoder():
    """Mock del modello CrossEncoder"""
    import numpy as np

    model = MagicMock()
    model.predict = MagicMock(return_value=np.array([0.8, 0.7, 0.6]))
    return model


@pytest.fixture
def mock_llm_client():
    """Mock del client LLM"""
    client = AsyncMock()
    client.generate_response = AsyncMock(
        return_value="Questa è una risposta generata dal mock LLM."
    )
    client.is_available = MagicMock(return_value=True)
    return client


# Fixtures per file di test
@pytest.fixture
def temp_pdf_file(tmp_path: Path) -> Path:
    """Crea un file PDF temporaneo per test"""
    pdf_file = tmp_path / "test.pdf"
    # Crea un PDF minimale usando PyMuPDF
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test PDF Content")
    doc.save(pdf_file)
    doc.close()
    return pdf_file


@pytest.fixture
def temp_html_file(tmp_path: Path) -> Path:
    """Crea un file HTML temporaneo per test"""
    html_file = tmp_path / "test.html"
    html_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Document</title></head>
    <body>
        <h1>Test Section</h1>
        <p>This is test content for HTML parsing.</p>
        <h2>Subsection</h2>
        <p>More test content here.</p>
    </body>
    </html>
    """
    html_file.write_text(html_content, encoding="utf-8")
    return html_file


# Utility fixtures
@pytest.fixture
def clean_test_data():
    """Pulisce dati di test dopo ogni test"""
    yield
    # Cleanup logic here if needed
    pass


@pytest.fixture(autouse=True)
def reset_loguru():
    """Reset logger per ogni test"""
    from loguru import logger

    logger.remove()
    logger.add(lambda msg: None, level="DEBUG")  # Sink silenzioso per test
    yield
    logger.remove()
