# ============================================
# FILE DI TEST/DEBUG - NON PER PRODUZIONE
# Creato da: Claude Code
# Data: 2025-10-18
# Scopo: Test semplice query tramite API
# ============================================

"""
Script semplic ato per testare una query tramite l'API REST.
"""

import asyncio
import httpx


async def test_query():
    """Testa la query problematica"""

    url_to_verify = "https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query"
    query = "quali sono le visualizzazioni previste per il comando da editor query"

    print("=" * 80)
    print("TEST QUERY TRAMITE API")
    print("=" * 80)
    print(f"\nQuery: {query}")
    print(f"URL atteso: {url_to_verify}")

    api_url = "http://localhost:8000"

    # 1. Verifica health
    print("\n1. Verifica connessione API...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{api_url}/health", timeout=5.0)
            if response.status_code == 200:
                print("  OK: API disponibile")
                health_data = response.json()
                stats = health_data.get("stats", {})
                retrieval_stats = stats.get("retrieval", {})
                vs_stats = retrieval_stats.get("vector_store", {})
                total_docs = vs_stats.get("total_points", 0)
                print(f"  Documenti indicizzati: {total_docs}")
            else:
                print(f"  ERRORE: Status {response.status_code}")
                return
        except Exception as e:
            print(f"  ERRORE: {e}")
            print("\nAvvia il server con: python -m rag_gestionale.api.main")
            return

    # 2. Esegui ricerca
    print(f"\n2. Eseguo ricerca...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            payload = {
                "query": query,
                "top_k": 10,
                "include_sources": True,
            }

            response = await client.post(f"{api_url}/search", json=payload)

            if response.status_code == 200:
                result = response.json()

                print(f"\nRISULTATO:")
                print(f"  Tipo query: {result.get('query_type', 'N/A')}")
                print(f"  Confidenza: {result.get('confidence', 0):.2%}")
                print(f"  Tempo: {result.get('processing_time_ms', 0) / 1000:.2f}s")

                answer = result.get("answer", "")
                print(f"\nRISPOSTA:")
                print(f"  {answer}")

                sources = result.get("sources", [])
                print(f"\nFONTI TROVATE: {len(sources)}")

                if sources:
                    print("\nTop 3 fonti:")
                    for idx, source in enumerate(sources[:3], 1):
                        chunk_data = source.get("chunk", {})
                        metadata = chunk_data.get("metadata", {})
                        score = source.get("score", 0)
                        title = metadata.get("title", "N/A")
                        url = metadata.get("source_url", "N/A")
                        print(f"\n  {idx}. {title} (Score: {score:.4f})")
                        print(f"     URL: {url}")
                        print(f"     Match URL atteso: {'SI' if url == url_to_verify else 'NO'}")

                        content = chunk_data.get("content", "")[:200]
                        print(f"     Contenuto: {content}...")

                    # Verifica se l'URL atteso è nelle fonti
                    urls_in_sources = [
                        s.get("chunk", {}).get("metadata", {}).get("source_url")
                        for s in sources
                    ]
                    if url_to_verify in urls_in_sources:
                        print(f"\nOK: URL atteso trovato nelle fonti")
                    else:
                        print(f"\nWARNING: URL atteso NON trovato nelle fonti")
                        print(f"URL presenti:")
                        for url in set(urls_in_sources):
                            print(f"  - {url}")
                else:
                    print("\nWARNING: Nessuna fonte trovata!")
                    print("Possibili cause:")
                    print("  1. URL non indicizzato nel sistema")
                    print("  2. Query troppo diversa dal contenuto indicizzato")
                    print("  3. Embedding/ricerca non funzionano correttamente")

            else:
                print(f"  ERRORE: Status {response.status_code}")
                print(f"  Dettaglio: {response.text[:500]}")

        except httpx.TimeoutException:
            print("  ERRORE: Timeout (>120s)")
        except Exception as e:
            print(f"  ERRORE: {e}")


if __name__ == "__main__":
    asyncio.run(test_query())
