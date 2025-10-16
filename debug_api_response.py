# ============================================
# FILE DI TEST/DEBUG - NON PER PRODUZIONE
# Creato da: Claude Code
# Data: 2025-10-16
# Scopo: Debug response API search
# ============================================

import asyncio
import json


async def debug_search_response():
    """Debug diretto del response search senza API"""
    from src.rag_gestionale.retrieval.hybrid_retriever import HybridRetriever
    from src.rag_gestionale.generation.generator import ResponseGenerator
    from src.rag_gestionale.core.models import QueryType

    print("=== Debug Search Response ===\n")

    # Inizializza componenti
    retriever = HybridRetriever()
    generator = ResponseGenerator()

    await retriever.initialize()

    # Esegui ricerca
    print("1. Ricerca...")
    search_results = await retriever.search(query="ratei", top_k=2)

    print(f"   Trovati {len(search_results)} risultati\n")

    # Verifica immagini nei SearchResult
    for idx, result in enumerate(search_results, 1):
        print(f"--- Risultato {idx} ---")
        print(f"Titolo: {result.chunk.metadata.title}")
        print(f"Score: {result.score:.3f}")
        print(f"Image IDs in chunk.metadata: {len(result.chunk.metadata.image_ids)}")
        print(f"Images in result: {len(result.images)}")

        if result.images:
            print("Immagini trovate:")
            for img in result.images[:2]:
                print(f"  - {img}")
        else:
            print("ATTENZIONE: Nessuna immagine nel SearchResult!")
            if result.chunk.metadata.image_ids:
                print(
                    f"  Ma il chunk ha {len(result.chunk.metadata.image_ids)} image_ids!"
                )
                print(f"  IDs: {result.chunk.metadata.image_ids[:3]}")

        print()

    # Genera response
    print("2. Generazione response...")
    query_type = QueryType.GENERAL
    response = await generator.generate_response(
        query="ratei",
        query_type=query_type,
        search_results=search_results,
        processing_time_ms=100,
    )

    print(f"   Sources in RAGResponse: {len(response.sources)}\n")

    # Verifica immagini nel RAGResponse
    for idx, source in enumerate(response.sources, 1):
        print(f"--- Source {idx} in RAGResponse ---")
        print(f"Titolo: {source.chunk.metadata.title}")
        print(f"Images in source: {len(source.images)}")
        if source.images:
            print("Immagini nel source:")
            for img in source.images[:2]:
                print(f"  - ID: {img.get('id')}")
                print(f"    URL: {img.get('image_url')}")
        else:
            print("ATTENZIONE: Nessuna immagine nel source!")
        print()

    # Serializza come JSON (come farebbe FastAPI)
    print("3. Serializzazione JSON...")
    try:
        json_str = response.model_dump_json(indent=2)
        data = json.loads(json_str)

        print(f"   Sources nel JSON: {len(data.get('sources', []))}")

        for idx, source in enumerate(data.get("sources", []), 1):
            images = source.get("images", [])
            print(f"   Source {idx}: {len(images)} immagini nel JSON")
            if not images and source.get("chunk", {}).get("metadata", {}).get(
                "image_ids"
            ):
                print(f"      PROBLEMA: image_ids presenti ma images vuoto!")

    except Exception as e:
        print(f"   Errore serializzazione: {e}")

    await retriever.close()


if __name__ == "__main__":
    asyncio.run(debug_search_response())
