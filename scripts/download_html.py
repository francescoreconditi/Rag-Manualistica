# ============================================
# FILE DI TEST/DEBUG - NON PER PRODUZIONE
# Creato da: Claude Code
# Data: 2025-10-18
# Scopo: Download e analisi HTML grezzo
# ============================================

"""
Scarica l'HTML della pagina e analizza cosa contiene.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from bs4 import BeautifulSoup


async def download_and_analyze(url: str):
    """Scarica e analizza HTML"""

    print("=" * 80)
    print("DOWNLOAD E ANALISI HTML")
    print("=" * 80)
    print(f"\nURL: {url}")

    # Download HTML
    print("\n1. Download HTML...")
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            html = response.text

            print(f"   OK: {len(html):,} caratteri scaricati")

            # Salva HTML grezzo
            output_file = "html_grezzo.html"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"   Salvato in: {output_file}")

        except Exception as e:
            print(f"   ERRORE: {e}")
            return

    # Analisi contenuto
    print("\n2. Analisi contenuto...")
    soup = BeautifulSoup(html, "html.parser")

    # Rimuovi script, style, nav, etc.
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text()
    text_clean = " ".join(text.split())

    print(f"   Testo totale: {len(text_clean):,} caratteri")

    # Cerca parole chiave
    print("\n3. Ricerca parole chiave...")
    keywords = [
        "visualizzazione",
        "visualizzazioni",
        "vista",
        "viste",
        "tabella",
        "grafico",
        "editor query",
        "comando"
    ]

    found_keywords = {}
    for keyword in keywords:
        count = text_clean.lower().count(keyword.lower())
        if count > 0:
            found_keywords[keyword] = count

            # Trova contesto (50 caratteri prima e dopo)
            keyword_lower = keyword.lower()
            text_lower = text_clean.lower()

            idx = text_lower.find(keyword_lower)
            if idx != -1:
                start = max(0, idx - 50)
                end = min(len(text_clean), idx + len(keyword) + 50)
                context = text_clean[start:end]
                print(f"\n   OK '{keyword}' trovata {count} volte")
                print(f"     Esempio: ...{context}...")

    if not found_keywords:
        print("\n   [X] NESSUNA parola chiave trovata!")
        print("   Questo significa che il testo non e' presente nell'HTML statico")
        print("   oppure e' generato dinamicamente via JavaScript.")

    # Estrai titolo e headers
    print("\n4. Struttura documento...")
    title = soup.find("title")
    if title:
        print(f"   Titolo: {title.get_text().strip()}")

    headers = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    print(f"\n   Headers trovati: {len(headers)}")
    for idx, h in enumerate(headers[:10], 1):  # Prime 10
        level = h.name
        text = h.get_text().strip()[:80]
        print(f"   {idx}. <{level}> {text}")

    if len(headers) > 10:
        print(f"   ... e altri {len(headers) - 10} headers")

    # Estrai paragrafi
    paragraphs = soup.find_all("p")
    print(f"\n   Paragrafi trovati: {len(paragraphs)}")
    if paragraphs:
        print(f"\n   Primi 3 paragrafi:")
        for idx, p in enumerate(paragraphs[:3], 1):
            text = p.get_text().strip()[:150]
            print(f"   {idx}. {text}...")

    # Conta immagini
    images = soup.find_all("img")
    print(f"\n   Immagini trovate: {len(images)}")
    if images:
        # Analizza prime 5 immagini
        print(f"\n   Prime 5 immagini:")
        for idx, img in enumerate(images[:5], 1):
            src = img.get("src", "")
            alt = img.get("alt", "")
            width = img.get("width", "?")
            height = img.get("height", "?")
            print(f"   {idx}. {src[:50]}... ({width}x{height}) alt='{alt}'")

    print("\n" + "=" * 80)
    print("CONCLUSIONE")
    print("=" * 80)

    if found_keywords:
        print("\n[OK] Le parole chiave SONO presenti nell'HTML")
        print("   Il problema potrebbe essere nel parsing/chunking")
        print("\n   Prossimo passo:")
        print("   1. Controlla il file 'html_grezzo.html' manualmente")
        print("   2. Cerca 'visualizzazioni' nel file")
        print("   3. Verifica se il testo e' in un tag particolare (div, span, etc.)")
    else:
        print("\n[X] Le parole chiave NON sono presenti nell'HTML statico")
        print("   Il contenuto e' probabilmente generato via JavaScript")
        print("\n   Soluzioni:")
        print("   1. Abilitare browser headless (Playwright)")
        print("   2. Fornire una versione statica/PDF della pagina")
        print("   3. Usare un URL alternativo con contenuto statico")


if __name__ == "__main__":
    url = "https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query"

    asyncio.run(download_and_analyze(url))
