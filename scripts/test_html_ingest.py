# ============================================
# FILE DI TEST/DEBUG - NON PER PRODUZIONE
# Creato da: Claude Code
# Data: 2025-10-18
# Scopo: Test ingestione HTML grosse con streaming batch processing
# ============================================

"""
Script di test per verificare le ottimizzazioni di ingestione HTML.
Testa:
- Pre-processing HTML (riduzione dimensione)
- Streaming batch processing per documenti grandi
- Timeout aumentati
- Batch size ridotto per CPU
"""

import asyncio
import sys
import time
from pathlib import Path

# Aggiungi il path della root del progetto
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from rag_gestionale.config.settings import get_settings
from rag_gestionale.ingest.coordinator import IngestionCoordinator


async def test_html_ingest():
    """Test ingestione HTML con le nuove ottimizzazioni"""

    logger.info("=" * 80)
    logger.info("TEST INGESTIONE HTML - Ottimizzazioni CPU")
    logger.info("=" * 80)

    # Mostra configurazione attuale
    settings = get_settings()
    logger.info("\nConfigurazione corrente:")
    logger.info(f"  - Batch size CPU: {settings.embedding.batch_size}")
    logger.info(f"  - Max HTML size: {settings.ingest.max_html_size_chars:,} chars")
    logger.info(f"  - Parsing timeout: {settings.ingest.parsing_timeout_seconds}s")
    logger.info(f"  - Embedding timeout: {settings.ingest.embedding_timeout_seconds}s")
    logger.info(f"  - Sections batch size: {settings.ingest.sections_batch_size}")
    logger.info(
        f"  - Streaming ingest: {'ABILITATO' if settings.ingest.enable_streaming_ingest else 'DISABILITATO'}"
    )

    # Crea coordinator
    coordinator = IngestionCoordinator()

    # Test URL di esempio (sostituisci con URL reali per il tuo test)
    test_urls = [
        "https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query"
        # Esempio: URL di una pagina grande del tuo gestionale
        # "http://cassiopea.centrosistemi.it/wiki/Modulo_Contabilita",
        # "http://cassiopea.centrosistemi.it/wiki/Desktop_Telematico",
    ]

    if not test_urls:
        logger.warning("\nNESSUN URL DI TEST SPECIFICATO!")
        logger.warning(
            "Modifica questo script e aggiungi URL reali alla lista 'test_urls'"
        )
        logger.warning(
            "Esempio: test_urls = ['http://cassiopea.centrosistemi.it/wiki/Modulo_Contabilita']"
        )
        return

    logger.info(f"\nInizio test con {len(test_urls)} URL")

    start_time = time.time()

    try:
        # Esegui ingestione
        chunks = await coordinator.ingest_from_urls(test_urls)

        elapsed = time.time() - start_time

        logger.info("\n" + "=" * 80)
        logger.info("TEST COMPLETATO CON SUCCESSO!")
        logger.info("=" * 80)
        logger.info(f"Tempo totale: {elapsed:.2f}s")
        logger.info(f"Chunk creati: {len(chunks)}")
        logger.info(f"Chunk/secondo: {len(chunks) / elapsed:.2f}")

        # Mostra statistiche per tipo
        from collections import Counter

        types = Counter([chunk.metadata.content_type for chunk in chunks])
        logger.info("\nDistribuzione per tipo:")
        for content_type, count in types.most_common():
            logger.info(f"  - {content_type}: {count} chunk")

        # Mostra esempio chunk
        if chunks:
            logger.info("\nEsempio primo chunk:")
            logger.info(f"  Titolo: {chunks[0].metadata.title}")
            logger.info(f"  Tipo: {chunks[0].metadata.content_type}")
            logger.info(f"  Contenuto (primi 200 chars): {chunks[0].content[:200]}...")

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("\n" + "=" * 80)
        logger.error("TEST FALLITO!")
        logger.error("=" * 80)
        logger.error(f"Errore dopo {elapsed:.2f}s: {e}")
        logger.exception("Stack trace completo:")
        raise


async def test_html_size_limits():
    """Test dei limiti di dimensione HTML"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST LIMITI DIMENSIONE HTML")
    logger.info("=" * 80)

    from rag_gestionale.ingest.html_parser import HTMLParser

    parser = HTMLParser()

    # Crea HTML di test molto grande
    large_html = "<html><body>"
    large_html += "<h1>Titolo Test</h1>"
    large_html += "<p>" + ("Testo di test. " * 10000) + "</p>"  # ~150K chars
    large_html += "<script>console.log('test');</script>" * 1000  # Script da rimuovere
    large_html += "</body></html>"

    original_size = len(large_html)
    logger.info(f"HTML originale: {original_size:,} caratteri")

    # Pre-processa
    processed_html = parser._preprocess_html(large_html)
    processed_size = len(processed_html)

    logger.info(f"HTML processato: {processed_size:,} caratteri")
    logger.info(
        f"Riduzione: {100 * (original_size - processed_size) / original_size:.1f}%"
    )

    settings = get_settings()
    if processed_size <= settings.ingest.max_html_size_chars:
        logger.info("OK: HTML rientra nel limite configurato")
    else:
        logger.warning(
            f"WARNING: HTML supera il limite di {settings.ingest.max_html_size_chars:,} chars"
        )


async def main():
    """Main test runner"""
    # Test 1: Limiti dimensione
    await test_html_size_limits()

    # Test 2: Ingestione reale (se configurato)
    await test_html_ingest()


if __name__ == "__main__":
    # Configura logging più verboso per i test
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )

    logger.info("Avvio test suite...")
    asyncio.run(main())
    logger.info("\nTest suite completata!")
