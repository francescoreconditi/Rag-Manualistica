# ============================================
# FILE DI TEST/DEBUG - NON PER PRODUZIONE
# Creato da: Claude Code
# Data: 2025-10-16
# Scopo: Verifica ID immagini salvati nel database
# ============================================

import asyncio


async def check_db_image_ids():
    """Verifica gli ID delle immagini salvati nel database"""
    from src.rag_gestionale.retrieval.lexical_search import LexicalSearch
    from src.rag_gestionale.config.settings import get_settings

    settings = get_settings()
    lexical = LexicalSearch()

    print("=== Verifica ID Immagini nel Database ===\n")

    try:
        await lexical.initialize()

        # Cerca documenti che contengono image_ids
        search_body = {
            "query": {"exists": {"field": "image_ids"}},
            "size": 10,
            "_source": ["chunk_id", "title", "image_ids"],
        }

        response = await lexical.client.search(
            index=lexical.index_name, body=search_body
        )

        print(f"Trovati {response['hits']['total']['value']} chunk con immagini\n")

        for hit in response["hits"]["hits"][:10]:
            source = hit["_source"]
            chunk_id = source.get("chunk_id", "N/A")
            title = source.get("title", "N/A")
            image_ids = source.get("image_ids", [])

            if image_ids:
                print(f"Chunk ID: {chunk_id}")
                print(f"Titolo: {title}")
                print(f"Numero immagini: {len(image_ids)}")
                print("Image IDs:")
                for img_id in image_ids[:5]:  # Max 5 per chunk
                    print(f"  - {img_id}")
                print()

    except Exception as e:
        print(f"Errore: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await lexical.close()


if __name__ == "__main__":
    asyncio.run(check_db_image_ids())
