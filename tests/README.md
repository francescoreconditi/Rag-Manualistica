# Test Suite - RAG Gestionale

Test suite completa per il sistema RAG specializzato per documentazione di gestionali.

## Struttura

```
tests/
├── unit/                 # Unit tests per singoli moduli
│   ├── test_chunker.py          # Test per IntelligentChunker
│   ├── test_vector_store.py     # Test per VectorStore (Qdrant)
│   ├── test_retriever.py        # Test per HybridRetriever
│   ├── test_generator.py        # Test per ResponseGenerator
│   └── test_pdf_parser.py       # Test per PDFParser
├── integration/          # Integration tests per API
│   ├── test_api_search.py       # Test endpoint /search
│   └── test_api_ingest.py       # Test endpoint /ingest
├── e2e/                  # End-to-end tests
│   └── test_full_pipeline.py    # Test flusso completo
├── conftest.py           # Fixtures globali e configurazione
└── README.md             # Questa documentazione
```

## Esecuzione Test

### Tutti i test

```bash
uv run pytest tests/
```

### Solo unit tests

```bash
uv run pytest tests/ -m "unit"
```

### Solo integration tests

```bash
uv run pytest tests/ -m "integration"
```

### Solo end-to-end tests

```bash
uv run pytest tests/ -m "e2e"
```

### Con coverage report

```bash
uv run pytest tests/ --cov=src/rag_gestionale --cov-report=html
```

Il report HTML sarà generato in `htmlcov/index.html`.

## Markers

I test sono organizzati con marker pytest:

- `@pytest.mark.unit` - Unit tests per moduli singoli
- `@pytest.mark.integration` - Integration tests per API e servizi
- `@pytest.mark.e2e` - End-to-end tests per flussi completi
- `@pytest.mark.slow` - Test lenti (tipicamente E2E)
- `@pytest.mark.requires_llm` - Test che richiedono LLM configurato
- `@pytest.mark.requires_qdrant` - Test che richiedono Qdrant running
- `@pytest.mark.requires_opensearch` - Test che richiedono OpenSearch running

### Escludere test lenti

```bash
uv run pytest tests/ -m "not slow"
```

### Solo test che non richiedono servizi esterni

```bash
uv run pytest tests/ -m "unit and not requires_qdrant and not requires_opensearch"
```

## Fixtures Principali

Le fixtures sono definite in [conftest.py](conftest.py):

### Dati di Test

- `sample_chunk_metadata` - Metadata di esempio per chunk
- `sample_document_chunk` - Chunk documento generico
- `sample_procedure_chunk` - Chunk di tipo procedura
- `sample_parameter_chunk` - Chunk di tipo parametro
- `sample_error_chunk` - Chunk di tipo errore
- `sample_chunks_list` - Lista di chunk vari
- `sample_search_result` - Risultato ricerca singolo
- `sample_search_results` - Lista risultati ricerca

### Mock Servizi

- `mock_qdrant_client` - Mock client Qdrant
- `mock_opensearch_client` - Mock client OpenSearch
- `mock_sentence_transformer` - Mock modello embedding
- `mock_cross_encoder` - Mock modello reranking
- `mock_llm_client` - Mock client LLM

### File Temporanei

- `temp_pdf_file` - File PDF temporaneo per test
- `temp_html_file` - File HTML temporaneo per test

## Obiettivi di Coverage

- **Target globale**: 80%+
- **Unit tests**: 90%+ per moduli core
- **Integration tests**: 80%+ per API endpoints
- **E2E tests**: Coverage completo dei flussi principali

## Best Practices

### Unit Tests

- Testare singole funzionalità in isolamento
- Usare mock per dipendenze esterne
- Un test = una funzionalità
- Naming: `test_<cosa_viene_testato>_<scenario>_<risultato_atteso>`

### Integration Tests

- Testare interazione tra componenti
- Mock solo servizi esterni (DB, API esterne)
- Verificare formato dati e contratti API
- Testare gestione errori

### E2E Tests

- Testare flussi utente completi
- Minimo mock possibile
- Verificare funzionamento end-to-end
- Includere scenari di errore e recovery

## Esempio Test

```python
import pytest
from src.rag_gestionale.ingest.chunker import IntelligentChunker

@pytest.mark.unit
class TestChunker:
    @pytest.fixture
    def chunker(self):
        return IntelligentChunker()

    def test_chunk_small_document(self, chunker, sample_document_chunk):
        # Arrange
        context = ChunkingContext(...)

        # Act
        chunks = chunker.chunk_document(sample_document_chunk, context)

        # Assert
        assert len(chunks) >= 1
        assert all(isinstance(c, DocumentChunk) for c in chunks)
```

## Debugging Test Falliti

### Visualizzare output completo

```bash
uv run pytest tests/ -vv -s
```

### Debug specifico test

```bash
uv run pytest tests/unit/test_chunker.py::TestChunker::test_specific -vv
```

### Vedere traceback completo

```bash
uv run pytest tests/ --tb=long
```

### Fermarsi al primo errore

```bash
uv run pytest tests/ -x
```

## CI/CD Integration

I test sono configurati per essere eseguiti in CI/CD con:

- Coverage minimo richiesto: 80%
- Timeout per test: 2 minuti (configurabile in pytest.ini)
- Report coverage in formato XML per integrazioni

## Troubleshooting

### Test falliscono per timeout

Aumentare il timeout in `pytest.ini`:

```ini
[pytest]
timeout = 300  # 5 minuti
```

### Mock non funzionano

Verificare che i path nei `patch()` siano corretti:

```python
# Corretto - patch dove viene importato
with patch("src.module.dependency.Class"):
    ...

# Sbagliato - patch dove è definito
with patch("external_lib.Class"):
    ...
```

### Fixture non trovate

Assicurarsi che `conftest.py` sia nella directory giusta e che pytest lo scopra automaticamente.

## Contribuire

Quando aggiungi nuovi test:

1. Segui la struttura esistente (unit/integration/e2e)
2. Usa i marker appropriati
3. Riutilizza fixture esistenti quando possibile
4. Documenta test complessi con docstring
5. Mantieni coverage > 80%

## Risorse

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [pytest-mock](https://pytest-mock.readthedocs.io/)
