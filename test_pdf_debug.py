# ============================================
# FILE DI TEST/DEBUG - NON PER PRODUZIONE
# Creato da: Claude Code
# Data: 2025-10-10
# Scopo: Debug ingestione PDF
# ============================================

"""
Script di debug per testare l'ingestione PDF
"""

import asyncio
import sys
from pathlib import Path

# Aggiungi il path del progetto
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag_gestionale.ingest.coordinator import IngestionCoordinator
from loguru import logger


async def test_pdf_ingestion():
    """Test ingestione PDF con logging dettagliato"""

    # Configura logging verboso
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="DEBUG",
    )

    pdf_url = "http://192.168.0.12:8000/t7adm_07501_711588.pdf"

    logger.info(f"=== TEST INGESTIONE PDF ===")
    logger.info(f"URL: {pdf_url}")

    coordinator = IngestionCoordinator()

    try:
        logger.info("Avvio ingestione...")
        chunks = await coordinator.ingest_from_urls([pdf_url])

        logger.info(f"\n=== RISULTATI ===")
        logger.info(f"Chunk totali estratti: {len(chunks)}")

        if chunks:
            logger.info("\n=== PRIMI 3 CHUNK ===")
            for i, chunk in enumerate(chunks[:3], 1):
                logger.info(f"\n--- Chunk {i} ---")
                logger.info(f"ID: {chunk.metadata.id}")
                logger.info(f"Titolo: {chunk.metadata.title}")
                logger.info(f"Content Type: {chunk.metadata.content_type}")
                logger.info(f"Pagine: {chunk.metadata.page_range}")
                logger.info(f"Lunghezza contenuto: {len(chunk.content)} caratteri")
                logger.info(f"Preview: {chunk.content[:200]}...")
        else:
            logger.warning("NESSUN CHUNK ESTRATTO! Verifica i log sopra per errori.")

    except Exception as e:
        logger.error(f"ERRORE durante test: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_pdf_ingestion())
