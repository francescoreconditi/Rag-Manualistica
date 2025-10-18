# ============================================
# FILE DI TEST/DEBUG - NON PER PRODUZIONE
# Creato da: Claude Code
# Data: 2025-10-18
# Scopo: Re-ingest URL con logging dettagliato
# ============================================

"""
Script per re-ingerire un URL specifico con logging dettagliato del parsing.
"""

import asyncio
import httpx


async def reingest_url(url: str):
    """Re-ingerisce un URL"""

    print("=" * 80)
    print("RE-INGESTIONE URL")
    print("=" * 80)
    print(f"\nURL: {url}")

    api_url = "http://localhost:8000"

    print("\n1. Avvio re-ingestione...")
    print("   Nota: Questo rimuoverà i chunk esistenti e ne creerà di nuovi")

    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            payload = {"urls": [url]}

            print(f"\n2. Invio richiesta POST a {api_url}/ingest...")
            response = await client.post(f"{api_url}/ingest", json=payload)

            if response.status_code == 200:
                result = response.json()

                print("\nRISULTATO INGESTIONE:")
                print(f"  Status: {result.get('status', 'N/A')}")
                print(f"  Messaggio: {result.get('message', 'N/A')}")
                print(f"  Chunk processati: {result.get('chunks_processed', 0)}")
                print(f"  Tempo: {result.get('processing_time_ms', 0) / 1000:.2f}s")

                if result.get("status") == "success":
                    print("\nOK: Re-ingestione completata con successo!")
                    print("\nProsegui con il test della query usando:")
                    print(f"  uv run python scripts/test_query_simple.py")
                else:
                    print("\nERRORE durante re-ingestione")

            else:
                print(f"\nERRORE: Status {response.status_code}")
                print(f"Dettaglio: {response.text[:500]}")

        except httpx.TimeoutException:
            print("\nERRORE: Timeout (>10 minuti)")
            print("L'ingestione potrebbe richiedere più tempo.")
        except Exception as e:
            print(f"\nERRORE: {e}")


if __name__ == "__main__":
    url_to_reingest = "https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query"

    print(f"\nATTENZIONE: Questo script reingerirà l'URL:")
    print(f"  {url_to_reingest}")
    print(f"\nI vecchi chunk verranno sostituiti con quelli nuovi.")
    print(f"Le ottimizzazioni FASE 2 saranno applicate.\n")

    input("Premi INVIO per continuare o CTRL+C per annullare...")

    asyncio.run(reingest_url(url_to_reingest))
