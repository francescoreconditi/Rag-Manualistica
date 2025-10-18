# Testing Guide - RAG Gestionale

Guida completa al testing per il progetto RAG Gestionale.

## Indice

- [Panoramica](#panoramica)
- [Setup](#setup)
- [Tipi di Test](#tipi-di-test)
- [Esecuzione Test](#esecuzione-test)
- [Best Practices](#best-practices)
- [Coverage](#coverage)
- [CI/CD](#cicd)
- [Troubleshooting](#troubleshooting)

## Panoramica

Il progetto utilizza una test suite completa con:

- **151+ test** organizzati in unit, integration ed E2E
- **Coverage target**: 80%+
- **Test automatici** in CI/CD
- **Pre-commit hooks** per validazione rapida

### Struttura

```
tests/
├── unit/              # 120+ test per moduli singoli
├── integration/       # 20+ test per API
├── e2e/              # 15+ test per flussi completi
├── performance/      # Benchmark test
├── conftest.py       # Fixtures globali
└── README.md         # Documentazione test
```

## Setup

### 1. Installazione Dipendenze

```bash
# Installa tutte le dipendenze development
uv pip install -e ".[dev]"

# Oppure solo dipendenze test
uv pip install pytest pytest-asyncio pytest-cov pytest-mock httpx
```

### 2. Configurazione Pre-commit (Opzionale)

```bash
# Installa pre-commit
uv pip install pre-commit

# Setup hooks
pre-commit install

# Test hooks manualmente
pre-commit run --all-files
```

### 3. Verifica Setup

```bash
# Esegui test rapidi
uv run pytest tests/ -m "unit and not slow" --no-cov -x

# Dovrebbe passare 110+ test in ~10 secondi
```

## Tipi di Test

### Unit Tests

Test di singole funzioni/classi in isolamento completo.

**Caratteristiche:**
- Veloci (<< 1 secondo ciascuno)
- Mock completo di dipendenze esterne
- Coverage > 90% per moduli core

**Esempi:**
```python
@pytest.mark.unit
def test_chunker_splits_document():
    chunker = IntelligentChunker()
    result = chunker.chunk_document(document, context)
    assert len(result) > 0
```

**Esecuzione:**
```bash
uv run pytest tests/ -m "unit"
```

### Integration Tests

Test di interazione tra componenti.

**Caratteristiche:**
- Mock solo servizi esterni (DB, API)
- Verificano contratti tra moduli
- Testano formato dati e error handling

**Esempi:**
```python
@pytest.mark.integration
async def test_search_api_endpoint(client):
    response = await client.post("/api/v1/search", json={"query": "test"})
    assert response.status_code == 200
```

**Esecuzione:**
```bash
uv run pytest tests/ -m "integration"
```

### End-to-End Tests

Test di flussi utente completi.

**Caratteristiche:**
- Minimo mock possibile
- Testano scenari reali
- Più lenti ma alta confidenza

**Esempi:**
```python
@pytest.mark.e2e
@pytest.mark.slow
async def test_full_ingest_search_flow(client):
    # Ingest
    await client.post("/api/v1/ingest", json={"urls": [...]})

    # Search
    response = await client.post("/api/v1/search", json={"query": "..."})
    assert len(response.json()["sources"]) > 0
```

**Esecuzione:**
```bash
uv run pytest tests/ -m "e2e"
```

### Performance Tests

Benchmark per componenti critici.

**Caratteristiche:**
- Misurano tempo esecuzione
- Rilevano regressioni performance
- Utili per ottimizzazione

**Esempi:**
```python
@pytest.mark.benchmark
def test_chunker_performance(benchmark):
    result = benchmark(chunker.chunk_document, large_doc)
    assert result is not None
```

**Esecuzione:**
```bash
uv run pytest tests/performance/ --benchmark-only
```

## Esecuzione Test

### Comandi Base

```bash
# Tutti i test
uv run pytest tests/

# Solo unit tests (rapido)
uv run pytest tests/ -m "unit"

# Solo integration tests
uv run pytest tests/ -m "integration"

# Solo E2E tests
uv run pytest tests/ -m "e2e"

# Test veloci (escludi slow)
uv run pytest tests/ -m "not slow"

# Con coverage
uv run pytest tests/ --cov=src/rag_gestionale --cov-report=html

# Verbose
uv run pytest tests/ -vv

# Stop al primo errore
uv run pytest tests/ -x

# Test paralleli (richiede pytest-xdist)
uv run pytest tests/ -n auto
```

### Script Utility

Usa lo script helper per configurazioni comuni:

```bash
# Unit tests
python scripts/run_tests.py --unit

# Integration tests
python scripts/run_tests.py --integration

# Tutti con coverage
python scripts/run_tests.py --all --coverage

# Test veloci
python scripts/run_tests.py --quick

# Verbose e stop al primo errore
python scripts/run_tests.py --unit --verbose --failfast
```

### Marker Personalizzati

```bash
# Solo test che non richiedono servizi esterni
pytest tests/ -m "unit and not requires_qdrant and not requires_opensearch"

# Solo test che richiedono LLM
pytest tests/ -m "requires_llm"

# Escludere test lenti
pytest tests/ -m "not slow"
```

## Best Practices

### 1. Test Naming

**Convenzione:** `test_<cosa>_<scenario>_<risultato>`

```python
# ✅ Buono
def test_chunker_splits_large_document_into_multiple_chunks():
    ...

# ❌ Cattivo
def test_chunker():
    ...
```

### 2. Arrange-Act-Assert Pattern

```python
def test_example():
    # Arrange - Setup
    chunker = IntelligentChunker()
    document = create_test_document()

    # Act - Esegui azione
    result = chunker.chunk_document(document, context)

    # Assert - Verifica risultato
    assert len(result) > 0
    assert all(isinstance(c, DocumentChunk) for c in result)
```

### 3. Fixture Riutilizzabili

```python
# conftest.py
@pytest.fixture
def sample_document():
    return DocumentChunk(content="...", metadata=...)

# test_module.py
def test_something(sample_document):
    # Usa fixture
    result = process(sample_document)
    assert result is not None
```

### 4. Mock Appropriati

```python
# ✅ Mock servizi esterni
@patch("module.external_api.call")
def test_with_mock(mock_call):
    mock_call.return_value = {"data": "test"}
    ...

# ❌ Non mockare codice interno inutilmente
# ✅ Invece, usa dipendency injection e fixture
```

### 5. Test Indipendenti

```python
# ✅ Ogni test è indipendente
def test_a():
    data = setup_data()
    assert process(data) == expected

def test_b():
    data = setup_data()  # Non dipende da test_a
    assert process(data) == expected

# ❌ Test dipendenti (fragili)
# state = None
# def test_a():
#     global state
#     state = ...
```

### 6. Assertion Chiare

```python
# ✅ Assert specifiche con messaggi
assert len(results) == 3, f"Expected 3 results, got {len(results)}"
assert user.name == "John", f"Wrong name: {user.name}"

# ✅ Usa pytest helpers
from pytest import approx
assert value == approx(0.85, abs=0.01)

# ✅ Verifica eccezioni
with pytest.raises(ValueError, match="Invalid input"):
    process(invalid_data)
```

### 7. Parametrizzazione

```python
@pytest.mark.parametrize("input,expected", [
    ("query1", QueryType.PROCEDURE),
    ("query2", QueryType.PARAMETER),
    ("query3", QueryType.ERROR),
])
def test_classify_query(input, expected):
    result = classifier.classify(input)
    assert result == expected
```

## Coverage

### Obiettivi

- **Globale**: 80%+
- **Moduli core**: 90%+
- **API**: 85%+

### Generare Report

```bash
# Report terminale
uv run pytest tests/ --cov=src/rag_gestionale --cov-report=term-missing

# Report HTML (interattivo)
uv run pytest tests/ --cov=src/rag_gestionale --cov-report=html
# Apri htmlcov/index.html

# Report XML (per CI/CD)
uv run pytest tests/ --cov=src/rag_gestionale --cov-report=xml
```

### Analizzare Coverage

```bash
# Mostra righe non coperte
uv run pytest tests/ --cov=src/rag_gestionale --cov-report=term-missing

# Fallisci se sotto soglia
uv run pytest tests/ --cov=src/rag_gestionale --cov-fail-under=80
```

### Aumentare Coverage

1. **Identifica gap**: Usa report HTML per vedere righe non coperte
2. **Aggiungi test**: Focalizza su branch non testati
3. **Edge cases**: Testa errori, eccezioni, casi limite
4. **Integration**: Aggiungi test che coprono interazioni

## CI/CD

### GitHub Actions

Il progetto usa GitHub Actions per CI/CD automatico.

**File**: `.github/workflows/tests.yml`

**Trigger:**
- Push su `main` e `develop`
- Pull Request

**Jobs:**
- Linting con ruff
- Unit tests con coverage
- Integration tests
- Upload coverage a Codecov

**Matrix testing:**
- OS: Ubuntu, Windows
- Python: 3.11, 3.12

### Configurazione Locale

Simula CI localmente:

```bash
# Lint
uv run ruff check src/
uv run ruff format --check src/

# Tests come in CI
uv run pytest tests/ -m "unit" --cov=src/rag_gestionale --cov-report=xml
```

### Badge Status

Aggiungi badge al README:

```markdown
![Tests](https://github.com/user/repo/workflows/Tests/badge.svg)
![Coverage](https://codecov.io/gh/user/repo/branch/main/graph/badge.svg)
```

## Troubleshooting

### Test Falliscono Localmente ma Passano in CI

**Causa:** Differenze ambiente (OS, Python version, dipendenze)

**Soluzione:**
```bash
# Verifica versione Python
python --version

# Reinstalla dipendenze
uv pip install -e ".[dev]" --force-reinstall

# Pulisci cache pytest
pytest --cache-clear
```

### Test Asincroni Falliscono

**Causa:** Event loop issues

**Soluzione:**
```python
# Usa fixture event_loop da conftest.py
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
```

### Mock Non Funzionano

**Causa:** Path sbagliato nel patch

**Soluzione:**
```python
# ✅ Patch dove viene IMPORTATO
@patch("module_that_imports.external.Class")

# ❌ NON dove è DEFINITO
@patch("external_library.Class")
```

### Coverage Troppo Basso

**Causa:** Test non coprono tutti i branch

**Soluzione:**
1. Genera report HTML: `pytest --cov=src --cov-report=html`
2. Apri `htmlcov/index.html`
3. Identifica righe rosse (non coperte)
4. Aggiungi test per quei casi

### Test Troppo Lenti

**Soluzione:**
```bash
# Profila test lenti
pytest tests/ --durations=10

# Esegui solo test veloci
pytest tests/ -m "not slow"

# Parallellizza
pytest tests/ -n auto
```

## Risorse

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)
- [Mock Object Patterns](https://martinfowler.com/articles/mocksArentStubs.html)

## Contribuire

Quando aggiungi nuovi test:

1. ✅ Segui naming convention
2. ✅ Usa fixture esistenti quando possibile
3. ✅ Marca con `@pytest.mark.unit/integration/e2e`
4. ✅ Documenta test complessi con docstring
5. ✅ Verifica coverage locale prima di commit
6. ✅ Esegui pre-commit hooks: `pre-commit run --all-files`

### Checklist Pull Request

Prima di creare PR con nuovi test:

- [ ] Tutti i test passano localmente
- [ ] Coverage >= 80%
- [ ] Lint pulito (ruff)
- [ ] Documentazione aggiornata se necessario
- [ ] Pre-commit hooks passano

## Domande Frequenti

**Q: Devo scrivere test per ogni funzione?**
A: Focus su logica di business, API pubbliche, edge cases. Non serve testare getter/setter triviali.

**Q: Quando uso mock?**
A: Mocka servizi esterni (DB, API, file I/O). Non mockare codice interno se possibile.

**Q: Quanti test devo scrivere?**
A: Abbastanza per avere confidenza nel codice. Punta a 80%+ coverage ma qualità > quantità.

**Q: Come testo codice asincrono?**
A: Usa `pytest-asyncio` e decora con `@pytest.mark.asyncio`.

**Q: I test devono essere veloci?**
A: Unit tests sì (< 1s). Integration/E2E possono essere più lenti ma marca con `@pytest.mark.slow`.
