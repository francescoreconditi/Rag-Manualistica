# ============================================
# FILE DI TEST/DEBUG - NON PER PRODUZIONE
# Creato da: Claude Code
# Data: 2025-10-18
# Scopo: Verifica contenuto effettivo dei chunk
# ============================================

"""
Verifica cosa contengono effettivamente i chunk nel database per un URL.
"""

import asyncio
import httpx


async def check_chunks():
    """Verifica i chunk via API"""

    api_url = "http://localhost:8000"
    url_to_check = "https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query"

    print("=" * 80)
    print("VERIFICA CONTENUTO CHUNK NEL DATABASE")
    print("=" * 80)

    # Test query
    query = "quali sono le visualizzazioni previste per il comando da editor query"
    print(f"\nQuery: {query}")

    print("\n1. Eseguo ricerca con top_k=10...")
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
                sources = result.get("sources", [])

                print(f"\nTrovate {len(sources)} fonti")

                # Filtra solo le fonti dall'URL che ci interessa
                relevant_sources = [
                    s for s in sources
                    if s.get("chunk", {}).get("metadata", {}).get("source_url") == url_to_check
                ]

                print(f"Fonti dall'URL target: {len(relevant_sources)}")

                if relevant_sources:
                    print("\n" + "=" * 80)
                    print("CHUNK DALL'URL TARGET")
                    print("=" * 80)

                    for idx, source in enumerate(relevant_sources, 1):
                        chunk_data = source.get("chunk", {})
                        metadata = chunk_data.get("metadata", {})
                        content = chunk_data.get("content", "")
                        score = source.get("score", 0)

                        print(f"\n--- Chunk {idx}/{len(relevant_sources)} ---")
                        print(f"Titolo: {metadata.get('title', 'N/A')}")
                        print(f"Score: {score:.4f}")
                        print(f"Content Type: {metadata.get('content_type', 'N/A')}")

                        # Conta le occorrenze di [Figura]
                        figura_count = content.count("[Figura:")
                        print(f"Placeholder [Figura:]: {figura_count}")

                        # Lunghezza contenuto
                        print(f"Lunghezza contenuto: {len(content)} caratteri")

                        # Mostra contenuto (primi 500 chars)
                        print(f"\nContenuto (primi 500 chars):")
                        print("-" * 40)
                        print(content[:500])
                        print("-" * 40)

                        # Verifica se contiene parole chiave utili
                        keywords = ["visualizzazione", "tabella", "grafico", "editor"]
                        found_keywords = [kw for kw in keywords if kw.lower() in content.lower()]
                        print(f"\nParole chiave trovate: {', '.join(found_keywords) if found_keywords else 'NESSUNA'}")

                        # Analisi composizione contenuto
                        text_without_figures = content.replace("[Figura:", "").replace("]", "")
                        useful_text_len = len(text_without_figures.strip())
                        figure_percentage = (figura_count * 20) / len(content) * 100 if len(content) > 0 else 0

                        print(f"\nAnalisi:")
                        print(f"  - Testo utile (senza [Figura]): {useful_text_len} chars")
                        print(f"  - Percentuale figure: ~{figure_percentage:.1f}%")

                    # Riepilogo
                    print("\n" + "=" * 80)
                    print("RIEPILOGO")
                    print("=" * 80)

                    total_figures = sum(s.get("chunk", {}).get("content", "").count("[Figura:") for s in relevant_sources)
                    avg_score = sum(s.get("score", 0) for s in relevant_sources) / len(relevant_sources)

                    print(f"\nTotale chunk dall'URL: {len(relevant_sources)}")
                    print(f"Totale placeholder [Figura:]: {total_figures}")
                    print(f"Score medio: {avg_score:.4f}")

                    # Diagnosi
                    print("\n DIAGNOSI:")
                    if total_figures > 50:
                        print("  [X] PROBLEMA: Troppi placeholder [Figura:]")
                        print("      Le immagini inquinano i chunk")
                        print("      AZIONE: Assicurati che RAG_IMAGE_STORAGE__ENABLED=false nel .env")
                        print("      AZIONE: Riavvia il server FastAPI")
                        print("      AZIONE: Re-ingerisci l'URL")
                    elif avg_score < 0.6:
                        print("  [!] ATTENZIONE: Score basso")
                        print("      Il contenuto non matcha bene la query")
                        print("      POSSIBILI CAUSE:")
                        print("        - Embedding model non ottimale per italiano")
                        print("        - Query troppo generica")
                        print("        - Chunking troppo granulare")
                    else:
                        print("  [OK] Chunk sembrano OK")
                        print("      Il problema potrebbe essere nella generazione della risposta")

                else:
                    print("\n[!] ATTENZIONE: Nessun chunk trovato dall'URL target!")
                    print("    URL target:", url_to_check)
                    print("\n    URLs presenti nei risultati:")
                    unique_urls = set()
                    for s in sources:
                        url = s.get("chunk", {}).get("metadata", {}).get("source_url", "N/A")
                        unique_urls.add(url)
                    for url in unique_urls:
                        print(f"      - {url}")

                    print("\n    POSSIBILI CAUSE:")
                    print("      1. URL non ancora indicizzato")
                    print("      2. URL indicizzato con formato diverso")
                    print("      3. Chunk dall'URL hanno score troppo basso e non entrano nella top-10")

            else:
                print(f"  ERRORE: Status {response.status_code}")
                print(f"  {response.text[:500]}")

        except Exception as e:
            print(f"  ERRORE: {e}")


if __name__ == "__main__":
    asyncio.run(check_chunks())
