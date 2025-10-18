# ============================================
# FILE DI TEST/DEBUG - NON PER PRODUZIONE
# Creato da: Claude Code
# Data: 2025-10-18
# Scopo: Verifica se un URL specifico è stato indicizzato
# ============================================

"""
Script per verificare se un URL è presente nel sistema RAG e analizzare i chunk estratti.
"""

import asyncio
import sys
from pathlib import Path

# Aggiungi il path della root del progetto
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from rag_gestionale.config.settings import get_settings
from rag_gestionale.retrieval.hybrid_retriever import HybridRetriever


async def check_url_indexed(url: str):
    """
    Verifica se un URL è stato indicizzato e mostra i chunk estratti.

    Args:
        url: URL da cercare (es. "https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query")
    """
    logger.info("=" * 80)
    logger.info(f"VERIFICA INDICIZZAZIONE URL")
    logger.info("=" * 80)
    logger.info(f"URL da cercare: {url}")

    settings = get_settings()

    # Crea retriever
    logger.info("\nInizializzazione retriever...")
    retriever = HybridRetriever()
    await retriever.initialize()

    # Ottieni statistiche vector store
    logger.info("\nStatistiche Vector Store:")
    stats = await retriever.vector_store.get_collection_stats()
    logger.info(f"  Totale documenti indicizzati: {stats.get('total_points', 0)}")

    # Cerca chunk per questo URL specifico
    logger.info(f"\nCerca chunk dall'URL: {url}")

    try:
        # Usa il vector store per cercare chunk con questo URL nei metadata
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        import asyncio

        search_filter = Filter(
            must=[FieldCondition(key="source_url", match=MatchValue(value=url))]
        )

        # Recupera chunk filtrati per URL (scroll è sincrono, eseguilo in thread)
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: retriever.vector_store.client.scroll(
                collection_name=settings.vector_store.collection_name,
                scroll_filter=search_filter,
                limit=100,  # Max 100 chunk
                with_payload=True,
                with_vectors=False,
            )
        )

        chunks = results[0] if results else []

        logger.info(f"\nRisultato: {len(chunks)} chunk trovati per questo URL")

        if chunks:
            logger.info("\n" + "=" * 80)
            logger.info("CHUNK TROVATI:")
            logger.info("=" * 80)

            for idx, chunk in enumerate(chunks, 1):
                payload = chunk.payload
                logger.info(f"\n--- Chunk {idx}/{len(chunks)} ---")
                logger.info(f"ID: {chunk.id}")
                logger.info(f"Titolo: {payload.get('title', 'N/A')}")
                logger.info(f"Tipo contenuto: {payload.get('content_type', 'N/A')}")
                logger.info(f"Modulo: {payload.get('module', 'N/A')}")
                logger.info(f"Section path: {payload.get('section_path', 'N/A')}")

                content = payload.get("content", "")
                logger.info(f"Contenuto (primi 200 chars): {content[:200]}...")
                logger.info(f"Lunghezza contenuto: {len(content)} caratteri")

                # Mostra breadcrumbs se presenti
                breadcrumbs = payload.get("breadcrumbs", [])
                if breadcrumbs:
                    logger.info(f"Breadcrumbs: {' > '.join(breadcrumbs)}")

                # Mostra image IDs se presenti
                image_ids = payload.get("image_ids", [])
                if image_ids:
                    logger.info(f"Immagini associate: {len(image_ids)}")

            # Analisi dei contenuti
            logger.info("\n" + "=" * 80)
            logger.info("ANALISI CONTENUTI:")
            logger.info("=" * 80)

            # Cerca parole chiave rilevanti
            keywords = [
                "visualizzazione",
                "visualizzazioni",
                "editor",
                "query",
                "comando",
            ]

            for keyword in keywords:
                matching_chunks = [
                    c
                    for c in chunks
                    if keyword.lower() in c.payload.get("content", "").lower()
                ]
                logger.info(f"Chunk contenenti '{keyword}': {len(matching_chunks)}")

            # Mostra tipi di contenuto
            from collections import Counter

            content_types = Counter(
                [c.payload.get("content_type", "N/A") for c in chunks]
            )
            logger.info(f"\nDistribuzione tipi contenuto:")
            for ctype, count in content_types.most_common():
                logger.info(f"  - {ctype}: {count} chunk")

        else:
            logger.warning("\n❌ URL NON TROVATO NEL SISTEMA!")
            logger.warning("Possibili cause:")
            logger.warning("  1. URL non ancora indicizzato")
            logger.warning("  2. Errore durante l'ingestione")
            logger.warning("  3. URL diverso da quello indicizzato (controlla esatto)")
            logger.warning(f"\nProva a eseguire ingestione:")
            logger.warning(f"  POST http://localhost:8000/ingest")
            logger.warning(f'  {{"urls": ["{url}"]}}')

    except Exception as e:
        logger.error(f"\nErrore durante la ricerca: {e}")
        logger.exception("Stack trace:")

    # Chiudi retriever
    await retriever.close()


async def test_search_query(query: str):
    """
    Testa una query di ricerca e mostra i risultati.

    Args:
        query: Query da testare
    """
    logger.info("\n" + "=" * 80)
    logger.info("TEST RICERCA QUERY")
    logger.info("=" * 80)
    logger.info(f"Query: {query}")

    # Crea retriever
    retriever = HybridRetriever()
    await retriever.initialize()

    # Esegui ricerca
    logger.info("\nEsecuzione ricerca...")
    results = await retriever.search(query, top_k=10)

    logger.info(f"\nRisultati: {len(results)} chunk trovati")

    if results:
        logger.info("\n" + "=" * 80)
        logger.info("TOP RISULTATI:")
        logger.info("=" * 80)

        for idx, result in enumerate(results[:5], 1):  # Top 5
            logger.info(f"\n--- Risultato {idx} (Score: {result.score:.4f}) ---")
            logger.info(f"Titolo: {result.chunk.metadata.title}")
            logger.info(f"URL: {result.chunk.metadata.source_url}")
            logger.info(f"Tipo: {result.chunk.metadata.content_type}")
            logger.info(f"Contenuto (primi 150 chars): {result.chunk.content[:150]}...")
    else:
        logger.warning("\n❌ NESSUN RISULTATO TROVATO!")
        logger.warning(
            "La query potrebbe non corrispondere a nessun documento indicizzato."
        )

    await retriever.close()


async def main():
    """Main"""
    # URL da verificare (quello menzionato dall'utente)
    url_to_check = "https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query"

    # Query dell'utente
    query_to_test = (
        "quali sono le visualizzazioni previste per il comando da editor query"
    )

    # 1. Verifica se URL è indicizzato
    await check_url_indexed(url_to_check)

    # 2. Testa la query di ricerca
    await test_search_query(query_to_test)


if __name__ == "__main__":
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )

    logger.info("Avvio verifica indicizzazione...\n")
    asyncio.run(main())
    logger.info("\n\nVerifica completata!")
