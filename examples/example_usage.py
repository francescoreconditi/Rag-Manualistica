"""
Esempi di utilizzo del sistema RAG gestionale.
Dimostra ingestione, ricerca e generazione di risposte.
"""

import asyncio
import json
from pathlib import Path

from src.rag_gestionale.ingest.coordinator import ingest_urls, ingest_directory
from src.rag_gestionale.retrieval.hybrid_retriever import search_documents
from src.rag_gestionale.generation.generator import generate_answer
from src.rag_gestionale.core.models import QueryType


async def example_ingest_url():
    """Esempio di ingestione da URL"""
    print("🚀 Esempio ingestione da URL...")

    # URL di esempio (manuale Teseo7)
    urls = [
        "https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query"
    ]

    try:
        chunks = await ingest_urls(urls)
        print(f"✅ Ingestione completata: {len(chunks)} chunk estratti")

        # Mostra dettagli primo chunk
        if chunks:
            chunk = chunks[0]
            print(f"📄 Primo chunk:")
            print(f"   Titolo: {chunk.metadata.title}")
            print(f"   Modulo: {chunk.metadata.module}")
            print(f"   Tipo: {chunk.metadata.content_type.value}")
            print(f"   Contenuto: {chunk.content[:200]}...")

    except Exception as e:
        print(f"❌ Errore ingestione: {e}")


async def example_search():
    """Esempio di ricerca"""
    print("\n🔍 Esempio ricerca...")

    queries = [
        "Come configurare una query SQL?",
        "Parametri per filtri avanzati",
        "Errore connessione database",
        "Impostazioni di visualizzazione tabellare",
    ]

    for query in queries:
        print(f"\nQuery: {query}")

        try:
            results = await search_documents(query, top_k=3)

            if results:
                print(f"Trovati {len(results)} risultati:")
                for i, result in enumerate(results, 1):
                    print(
                        f"  {i}. {result.chunk.metadata.title} (score: {result.score:.3f})"
                    )
            else:
                print("  ❌ Nessun risultato trovato")

        except Exception as e:
            print(f"  ❌ Errore ricerca: {e}")


async def example_full_pipeline():
    """Esempio pipeline completa: ingestione + ricerca + generazione"""
    print("\n🔄 Esempio pipeline completa...")

    # Simula risultati di ricerca per demo
    from src.rag_gestionale.core.models import (
        DocumentChunk,
        ChunkMetadata,
        SearchResult,
        ContentType,
        SourceFormat,
    )
    from datetime import datetime

    # Crea chunk di esempio
    metadata = ChunkMetadata(
        id="example_chunk_001",
        title="Configurazione Query SQL",
        breadcrumbs=["Desktop Teseo7", "Editor Query", "Configurazione"],
        section_level=2,
        section_path="editor_query/configurazione",
        content_type=ContentType.PROCEDURE,
        version="7.0",
        module="Desktop Teseo7",
        source_url="https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query",
        source_format=SourceFormat.HTML,
        lang="it",
        hash="example_hash",
        updated_at=datetime.now(),
    )

    chunk = DocumentChunk(
        content="""
Per configurare una query SQL nell'Editor Query:

1. Aprire il menu Strumenti > Editor Query
2. Selezionare la connessione al database
3. Impostare i parametri di configurazione:
   - Timeout query: 30 secondi
   - Modalità debug: Abilitata
   - Formato output: Tabellare
4. Verificare la sintassi SQL
5. Eseguire la query con F5

Attenzione: Verificare sempre i permessi sul database prima dell'esecuzione.
        """.strip(),
        metadata=metadata,
    )

    # Simula risultato di ricerca
    search_result = SearchResult(
        chunk=chunk, score=0.95, explanation="Exact match for SQL query configuration"
    )

    # Genera risposta
    query = "Come configurare una query SQL?"
    response = generate_answer(
        query=query,
        query_type=QueryType.PROCEDURE,
        search_results=[search_result],
        processing_time_ms=150,
    )

    print(f"Query: {query}")
    print(f"Tipo: {response.query_type.value}")
    print(f"Confidenza: {response.confidence:.2f}")
    print(f"Tempo: {response.processing_time_ms}ms")
    print(f"\nRisposta:\n{response.answer}")


async def example_test_cases():
    """Crea file di test cases per valutazione"""
    print("\n📝 Creazione test cases...")

    test_cases = [
        {
            "query": "Come impostare timeout query?",
            "expected_type": "parameter",
            "category": "configurazione",
        },
        {
            "query": "Procedura per creare nuova connessione database",
            "expected_type": "procedure",
            "category": "setup",
        },
        {
            "query": "Errore SQL-001 connessione fallita",
            "expected_type": "error",
            "category": "troubleshooting",
        },
        {
            "query": "Cosa sono i filtri avanzati?",
            "expected_type": "general",
            "category": "concetti",
        },
        {
            "query": "Impostazione modalità debug query",
            "expected_type": "parameter",
            "category": "configurazione",
        },
    ]

    # Salva test cases
    test_file = Path("examples/test_cases.json")
    test_file.parent.mkdir(exist_ok=True)

    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(test_cases, f, indent=2, ensure_ascii=False)

    print(f"✅ Test cases salvati in: {test_file}")
    print(f"📊 Totale test: {len(test_cases)}")

    # Mostra distribuzione per tipo
    from collections import Counter

    type_counts = Counter(tc["expected_type"] for tc in test_cases)
    print("📈 Distribuzione per tipo:")
    for type_name, count in type_counts.items():
        print(f"   {type_name}: {count}")


async def main():
    """Esegue tutti gli esempi"""
    print("🤖 Esempi Sistema RAG Gestionale\n")

    # Commenta queste righe se non hai i servizi (Qdrant/OpenSearch) attivi
    # await example_ingest_url()
    # await example_search()

    # Questi esempi funzionano sempre
    await example_full_pipeline()
    await example_test_cases()

    print("\n✅ Esempi completati!")
    print("\n📚 Per avviare l'API:")
    print("   python -m src.rag_gestionale.api.main")
    print("\n🔧 Per usare la CLI:")
    print("   python -m src.rag_gestionale.api.cli --help")


if __name__ == "__main__":
    asyncio.run(main())
