# ============================================
# FILE DI TEST/DEBUG - NON PER PRODUZIONE
# Creato da: Claude Code
# Data: 2025-09-30
# Scopo: Verifica contenuto del vector store
# ============================================

import asyncio
from qdrant_client import AsyncQdrantClient
from loguru import logger


async def check_vector_store():
    """Verifica lo stato del vector store"""

    client = AsyncQdrantClient(host="localhost", port=6333, check_compatibility=False)

    try:
        # Ottieni info collection
        collection_info = await client.get_collection("gestionale_docs")

        print("\n" + "=" * 60)
        print("INFO COLLECTION GESTIONALE_DOCS")
        print("=" * 60)
        print(f"Numero di punti: {collection_info.points_count}")
        print(f"Dimensione vettori: {collection_info.config.params.vectors.size}")
        print(f"Distanza: {collection_info.config.params.vectors.distance}")
        print("=" * 60 + "\n")

        if collection_info.points_count == 0:
            print("⚠️  PROBLEMA: La collection è VUOTA!")
            print("Soluzione: Devi re-indicizzare i documenti tramite l'app Streamlit")
            return

        # Ottieni alcuni esempi di punti
        print("\n" + "=" * 60)
        print("ESEMPIO DI PUNTI (primi 3)")
        print("=" * 60)

        scroll_result = await client.scroll(
            collection_name="gestionale_docs", limit=3, with_payload=True
        )

        for i, point in enumerate(scroll_result[0], 1):
            print(f"\nPunto {i}:")
            print(f"  ID: {point.id}")
            if point.payload:
                print(f"  Titolo: {point.payload.get('title', 'N/A')}")
                print(f"  URL: {point.payload.get('source_url', 'N/A')}")
                print(f"  Contenuto (primi 100 char): {point.payload.get('content', '')[:100]}...")

        # Test ricerca
        print("\n" + "=" * 60)
        print("TEST RICERCA: 'stampa di bilancio'")
        print("=" * 60)

        # Genera embedding fittizio (dovresti usare lo stesso modello dell'app)
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("BAAI/bge-m3", device="cpu")
        query_embedding = model.encode("stampa di bilancio").tolist()

        search_results = await client.search(
            collection_name="gestionale_docs",
            query_vector=query_embedding,
            limit=5,
            with_payload=True,
        )

        if not search_results:
            print("⚠️  Nessun risultato trovato!")
        else:
            print(f"\nTrovati {len(search_results)} risultati:\n")
            for i, result in enumerate(search_results, 1):
                print(f"{i}. Score: {result.score:.4f}")
                print(f"   Titolo: {result.payload.get('title', 'N/A')}")
                print(
                    f"   Contenuto: {result.payload.get('content', '')[:80]}...\n"
                )

    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        print(
            "\nPossibile causa: Qdrant non è in esecuzione o la collection non esiste"
        )

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(check_vector_store())