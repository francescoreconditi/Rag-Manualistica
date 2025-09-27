"""
CLI per gestione del sistema RAG.
Comandi per ingestione, test e manutenzione.
"""

import asyncio
import json
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import track

from ..ingest.coordinator import IngestionCoordinator
from ..retrieval.hybrid_retriever import HybridRetriever
from ..generation.generator import ResponseGenerator
from ..config.settings import get_settings

console = Console()


@click.group()
def cli():
    """CLI per sistema RAG gestionale"""
    pass


@cli.command()
@click.argument("urls", nargs=-1)
@click.option("--output", "-o", help="File di output per statistiche")
def ingest_urls(urls: List[str], output: Optional[str]):
    """Ingestione da URL"""
    if not urls:
        console.print("❌ Nessun URL specificato", style="red")
        return

    async def run_ingest():
        coordinator = IngestionCoordinator()

        console.print(f"🚀 Avvio ingestione di {len(urls)} URL...")

        chunks = await coordinator.ingest_from_urls(list(urls))

        # Indicizza nel retriever
        retriever = HybridRetriever()
        await retriever.initialize()

        try:
            await retriever.add_chunks(chunks)

            stats = {
                "urls_processed": len(urls),
                "chunks_created": len(chunks),
                "status": "success",
            }

            # Salva statistiche
            if output:
                with open(output, "w") as f:
                    json.dump(stats, f, indent=2)

            console.print(
                f"✅ Ingestione completata: {len(chunks)} chunk", style="green"
            )

        finally:
            await retriever.close()

    asyncio.run(run_ingest())


@cli.command()
@click.argument("directory")
@click.option("--recursive", "-r", is_flag=True, help="Ricerca ricorsiva")
def ingest_dir(directory: str, recursive: bool):
    """Ingestione da directory"""
    dir_path = Path(directory)
    if not dir_path.exists():
        console.print(f"❌ Directory non trovata: {directory}", style="red")
        return

    async def run_ingest():
        coordinator = IngestionCoordinator()

        console.print(f"📁 Ingestione directory: {directory}")

        chunks = await coordinator.ingest_from_directory(directory)

        # Indicizza
        retriever = HybridRetriever()
        await retriever.initialize()

        try:
            await retriever.add_chunks(chunks)
            console.print(
                f"✅ Ingestione completata: {len(chunks)} chunk", style="green"
            )
        finally:
            await retriever.close()

    asyncio.run(run_ingest())


@cli.command()
@click.argument("query")
@click.option("--top-k", "-k", default=5, help="Numero di risultati")
@click.option("--module", "-m", help="Filtro per modulo")
@click.option("--format", "-f", type=click.Choice(["json", "table"]), default="table")
def search(query: str, top_k: int, module: Optional[str], format: str):
    """Ricerca nella documentazione"""

    async def run_search():
        retriever = HybridRetriever()
        generator = ResponseGenerator()

        await retriever.initialize()

        try:
            # Filtri
            filters = {}
            if module:
                filters["module"] = module

            # Ricerca
            results = await retriever.search(query, top_k, filters)

            if not results:
                console.print("❌ Nessun risultato trovato", style="red")
                return

            # Classifica query
            query_type = retriever.query_classifier.classify_query(query)

            # Genera risposta
            response = generator.generate_response(query, query_type, results, 0)

            if format == "json":
                # Output JSON
                output = {
                    "query": query,
                    "query_type": query_type.value,
                    "answer": response.answer,
                    "confidence": response.confidence,
                    "sources": [
                        {
                            "title": r.chunk.metadata.title,
                            "score": r.score,
                            "module": r.chunk.metadata.module,
                            "url": r.chunk.metadata.source_url,
                        }
                        for r in results
                    ],
                }
                console.print_json(json.dumps(output, indent=2, ensure_ascii=False))
            else:
                # Output tabella
                console.print(f"\n🔍 Query: {query}", style="bold blue")
                console.print(f"📝 Tipo: {query_type.value}", style="yellow")
                console.print(
                    f"🎯 Confidenza: {response.confidence:.2f}", style="green"
                )

                console.print(f"\n📋 Risposta:", style="bold")
                console.print(response.answer)

                # Tabella risultati
                table = Table(title=f"Top {len(results)} Risultati")
                table.add_column("Score", style="cyan")
                table.add_column("Titolo", style="green")
                table.add_column("Modulo", style="yellow")
                table.add_column("Tipo", style="magenta")

                for result in results:
                    table.add_row(
                        f"{result.score:.3f}",
                        result.chunk.metadata.title[:50] + "..."
                        if len(result.chunk.metadata.title) > 50
                        else result.chunk.metadata.title,
                        result.chunk.metadata.module,
                        result.chunk.metadata.content_type.value,
                    )

                console.print(table)

        finally:
            await retriever.close()

    asyncio.run(run_search())


@cli.command()
def stats():
    """Statistiche del sistema"""

    async def show_stats():
        retriever = HybridRetriever()
        await retriever.initialize()

        try:
            stats = await retriever.get_stats()

            # Tabella statistiche
            table = Table(title="📊 Statistiche Sistema RAG")
            table.add_column("Componente", style="cyan")
            table.add_column("Metrica", style="yellow")
            table.add_column("Valore", style="green")

            # Vector store
            if "vector_store" in stats:
                vs_stats = stats["vector_store"]
                table.add_row(
                    "Vector Store", "Documenti", str(vs_stats.get("total_points", 0))
                )
                table.add_row(
                    "", "Dimensione vettore", str(vs_stats.get("vector_size", 0))
                )
                table.add_row("", "Distanza", str(vs_stats.get("distance", "N/A")))

            # Lexical search
            if "lexical_search" in stats:
                ls_stats = stats["lexical_search"]
                table.add_row(
                    "Lexical Search",
                    "Documenti",
                    str(ls_stats.get("document_count", 0)),
                )
                table.add_row(
                    "",
                    "Dimensione indice",
                    f"{ls_stats.get('store_size', 0) // 1024} KB",
                )

            # Configurazione
            settings = get_settings()
            table.add_row("Configurazione", "K Dense", str(settings.retrieval.k_dense))
            table.add_row("", "K Lexical", str(settings.retrieval.k_lexical))
            table.add_row("", "Modello Embedding", settings.embedding.model_name)
            table.add_row("", "Modello Reranker", settings.retrieval.reranker_model)

            console.print(table)

        finally:
            await retriever.close()

    asyncio.run(show_stats())


@cli.command()
@click.argument("test_file")
def test(test_file: str):
    """Esegue test batch da file JSON"""

    test_path = Path(test_file)
    if not test_path.exists():
        console.print(f"❌ File test non trovato: {test_file}", style="red")
        return

    # Carica test cases
    with open(test_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    async def run_tests():
        retriever = HybridRetriever()
        generator = ResponseGenerator()

        await retriever.initialize()

        try:
            results = []

            for test_case in track(test_cases, description="Esecuzione test..."):
                query = test_case["query"]
                expected_type = test_case.get("expected_type")

                # Ricerca
                search_results = await retriever.search(query, 5)

                if search_results:
                    # Classifica
                    query_type = retriever.query_classifier.classify_query(query)

                    # Genera risposta
                    response = generator.generate_response(
                        query, query_type, search_results, 0
                    )

                    result = {
                        "query": query,
                        "predicted_type": query_type.value,
                        "expected_type": expected_type,
                        "confidence": response.confidence,
                        "num_sources": len(search_results),
                        "top_score": search_results[0].score,
                        "correct_type": query_type.value == expected_type
                        if expected_type
                        else None,
                    }
                else:
                    result = {
                        "query": query,
                        "predicted_type": "none",
                        "expected_type": expected_type,
                        "confidence": 0.0,
                        "num_sources": 0,
                        "top_score": 0.0,
                        "correct_type": False if expected_type else None,
                    }

                results.append(result)

            # Report
            console.print("\n📊 Risultati Test:", style="bold")

            if any(r["correct_type"] is not None for r in results):
                correct = sum(1 for r in results if r["correct_type"])
                total = sum(1 for r in results if r["correct_type"] is not None)
                accuracy = correct / total if total > 0 else 0
                console.print(
                    f"🎯 Accuratezza classificazione: {accuracy:.2%}", style="green"
                )

            avg_confidence = sum(r["confidence"] for r in results) / len(results)
            console.print(f"📈 Confidenza media: {avg_confidence:.2f}", style="blue")

            found_results = sum(1 for r in results if r["num_sources"] > 0)
            coverage = found_results / len(results)
            console.print(f"📋 Coverage: {coverage:.2%}", style="cyan")

            # Salva risultati dettagliati
            output_file = test_path.with_suffix(".results.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            console.print(f"💾 Risultati salvati in: {output_file}", style="yellow")

        finally:
            await retriever.close()

    asyncio.run(run_tests())


@cli.command()
def serve():
    """Avvia server API"""
    import uvicorn
    from .main import app

    settings = get_settings()

    console.print("🚀 Avvio server API...", style="green")
    console.print(
        f"📍 Indirizzo: http://{settings.api_host}:{settings.api_port}", style="blue"
    )
    console.print(
        f"📚 Docs: http://{settings.api_host}:{settings.api_port}/docs", style="cyan"
    )

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
    )


if __name__ == "__main__":
    cli()
