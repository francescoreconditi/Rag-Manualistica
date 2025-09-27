"""
Sistema di retrieval ibrido con Vector + BM25 + Reranking.
Ottimizzato per query su documentazione di gestionali.
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

from loguru import logger
from sentence_transformers import CrossEncoder

from ..core.models import DocumentChunk, SearchResult, QueryType
from ..config.settings import get_settings
from .vector_store import VectorStore
from .lexical_search import LexicalSearch


class QueryClassifier:
    """Classificatore di query per routing intelligente"""

    def __init__(self):
        # Pattern per classificazione query
        self.parameter_patterns = [
            r"\b(?:param|impostaz|valori|predefin|default|range)\b",
            r"\bcome\s+(?:impostare|configurare|settare)\b",
            r"\bdove\s+(?:trovo|si trova)\b",
            r"\bvalori?\s+(?:ammessi|possibili|consentiti)\b",
        ]

        self.procedure_patterns = [
            r"\bcome\s+(?:fare|eseguire|effettuare)\b",
            r"\b(?:procedura|processo|step|passi)\b",
            r"\bper\s+(?:creare|generare|stampare|inviare)\b",
            r"\b(?:configurare|impostare)\s+.*\b",
        ]

        self.error_patterns = [
            r"\b[A-Z]{2,4}-?\d{2,4}\b",  # Codici errore
            r"\b(?:errore|error|avviso|warning|codice)\b",
            r"\bnon\s+(?:funziona|va|riesco)\b",
        ]

    def classify_query(self, query: str) -> QueryType:
        """
        Classifica la query per ottimizzare il retrieval

        Args:
            query: Query dell'utente

        Returns:
            Tipo di query classificato
        """
        query_lower = query.lower()

        import re

        # Controlla errori per primi (più specifici)
        if any(re.search(pattern, query_lower) for pattern in self.error_patterns):
            return QueryType.ERROR

        # Controlla parametri
        if any(re.search(pattern, query_lower) for pattern in self.parameter_patterns):
            return QueryType.PARAMETER

        # Controlla procedure
        if any(re.search(pattern, query_lower) for pattern in self.procedure_patterns):
            return QueryType.PROCEDURE

        return QueryType.GENERAL


class HybridRetriever:
    """Retriever ibrido Vector + Lexical con reranking"""

    def __init__(self):
        self.settings = get_settings()
        self.vector_store = VectorStore()
        self.lexical_search = LexicalSearch()
        self.query_classifier = QueryClassifier()
        self.reranker: Optional[CrossEncoder] = None

    async def initialize(self):
        """Inizializza tutti i componenti"""
        # Inizializza stores
        await self.vector_store.initialize()
        await self.lexical_search.initialize()

        # Carica reranker
        logger.info(f"Caricamento reranker: {self.settings.retrieval.reranker_model}")
        loop = asyncio.get_event_loop()
        self.reranker = await loop.run_in_executor(
            None,
            lambda: CrossEncoder(self.settings.retrieval.reranker_model),
        )

        logger.info("Hybrid retriever inizializzato")

    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        query_type: Optional[QueryType] = None,
    ) -> List[SearchResult]:
        """
        Ricerca ibrida principale

        Args:
            query: Query di ricerca
            top_k: Numero di risultati finali
            filters: Filtri sui metadati
            query_type: Tipo di query (se non specificato, viene classificato)

        Returns:
            Lista di risultati riordinati e deduplicati
        """
        if top_k is None:
            top_k = self.settings.retrieval.k_final

        # Classifica query se non specificato
        if query_type is None:
            query_type = self.query_classifier.classify_query(query)

        logger.debug(f"Query classificata come: {query_type.value}")

        # Ottieni candidati da entrambi i sistemi
        vector_results, lexical_results = await self._get_candidates(
            query, filters, query_type
        )

        # Combina e deduplica risultati
        combined_results = self._combine_results(vector_results, lexical_results)

        # Reranking
        if len(combined_results) > self.settings.retrieval.k_final:
            reranked_results = await self._rerank_results(query, combined_results)
        else:
            reranked_results = combined_results

        # Diversificazione (evita troppi risultati dalla stessa sezione)
        diversified_results = self._diversify_results(reranked_results)

        # Tronca ai risultati finali
        return diversified_results[:top_k]

    async def _get_candidates(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        query_type: QueryType,
    ) -> Tuple[List[SearchResult], List[SearchResult]]:
        """Ottiene candidati da vector e lexical search"""

        # Adatta parametri basati sul tipo di query
        k_dense, k_lexical = self._get_k_values(query_type)

        # Esegui ricerche in parallelo
        vector_task = self.vector_store.search(
            query=query,
            top_k=k_dense,
            filters=filters,
        )

        lexical_task = self.lexical_search.search(
            query=query,
            top_k=k_lexical,
            filters=filters,
            boost_params=self._get_boost_params(query_type),
        )

        vector_results, lexical_results = await asyncio.gather(
            vector_task, lexical_task
        )

        logger.debug(
            f"Candidati: {len(vector_results)} vector, {len(lexical_results)} lexical"
        )

        return vector_results, lexical_results

    def _get_k_values(self, query_type: QueryType) -> Tuple[int, int]:
        """Ottiene valori k basati sul tipo di query"""
        base_dense = self.settings.retrieval.k_dense
        base_lexical = self.settings.retrieval.k_lexical

        if query_type == QueryType.ERROR:
            # Per errori, favorisci lexical (codici esatti)
            return base_dense // 2, base_lexical * 2
        elif query_type == QueryType.PARAMETER:
            # Per parametri, bilanciato con leggera preferenza lexical
            return int(base_dense * 0.7), int(base_lexical * 1.3)
        elif query_type == QueryType.PROCEDURE:
            # Per procedure, favorisci semantic
            return int(base_dense * 1.3), int(base_lexical * 0.7)
        else:
            # Query generali - valori di default
            return base_dense, base_lexical

    def _get_boost_params(self, query_type: QueryType) -> Dict[str, float]:
        """Ottiene parametri di boost basati sul tipo di query"""
        base_boosts = {
            "title": self.settings.retrieval.title_boost,
            "breadcrumbs": self.settings.retrieval.breadcrumbs_boost,
            "param_name": self.settings.retrieval.param_name_boost,
            "error_code": self.settings.retrieval.error_code_boost,
        }

        if query_type == QueryType.ERROR:
            # Boost massimo per codici errore
            base_boosts["error_code"] *= 2.0
        elif query_type == QueryType.PARAMETER:
            # Boost per nomi parametri
            base_boosts["param_name"] *= 1.5
        elif query_type == QueryType.PROCEDURE:
            # Boost per titoli procedurali
            base_boosts["title"] *= 1.3

        return base_boosts

    def _combine_results(
        self, vector_results: List[SearchResult], lexical_results: List[SearchResult]
    ) -> List[SearchResult]:
        """Combina e deduplica risultati da vector e lexical"""
        seen_chunks = {}
        combined = []

        # Normalizza scores (0-1) per comparabilità
        max_vector_score = max([r.score for r in vector_results], default=1.0)
        max_lexical_score = max([r.score for r in lexical_results], default=1.0)

        # Aggiungi risultati vector
        for result in vector_results:
            chunk_id = result.chunk.metadata.id
            normalized_score = result.score / max_vector_score
            result.score = normalized_score
            result.explanation = f"Vector: {normalized_score:.3f}"

            seen_chunks[chunk_id] = result
            combined.append(result)

        # Aggiungi risultati lexical (combina se già visti)
        for result in lexical_results:
            chunk_id = result.chunk.metadata.id
            normalized_score = result.score / max_lexical_score

            if chunk_id in seen_chunks:
                # Combina scores (media pesata)
                existing_result = seen_chunks[chunk_id]
                combined_score = (existing_result.score * 0.6) + (
                    normalized_score * 0.4
                )
                existing_result.score = combined_score
                existing_result.explanation = f"Hybrid: {combined_score:.3f}"
            else:
                result.score = normalized_score
                result.explanation = f"Lexical: {normalized_score:.3f}"
                seen_chunks[chunk_id] = result
                combined.append(result)

        # Ordina per score combinato
        combined.sort(key=lambda x: x.score, reverse=True)

        return combined

    async def _rerank_results(
        self, query: str, results: List[SearchResult]
    ) -> List[SearchResult]:
        """Reranking con cross-encoder"""
        if not self.reranker or len(results) <= 1:
            return results

        # Prepara coppie query-document per reranker
        pairs = []
        for result in results:
            # Usa titolo + inizio contenuto per reranking
            doc_text = f"{result.chunk.metadata.title}. {result.chunk.content[:200]}"
            pairs.append([query, doc_text])

        # Calcola scores di reranking
        loop = asyncio.get_event_loop()
        rerank_scores = await loop.run_in_executor(
            None, lambda: self.reranker.predict(pairs)
        )

        # Aggiorna scores e ordina
        for i, result in enumerate(results):
            # Combina score originale con rerank (weighted)
            original_score = result.score
            rerank_score = float(rerank_scores[i])
            combined_score = (original_score * 0.3) + (rerank_score * 0.7)

            result.score = combined_score
            result.explanation = f"Reranked: {combined_score:.3f}"

        # Ordina per nuovo score
        results.sort(key=lambda x: x.score, reverse=True)

        logger.debug(f"Reranking completato su {len(results)} risultati")
        return results

    def _diversify_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Diversifica risultati per evitare troppi dalla stessa sezione"""
        diversified = []
        section_counts = defaultdict(int)
        max_per_section = self.settings.retrieval.diversification_threshold

        for result in results:
            section_path = result.chunk.metadata.section_path or "unknown"

            if section_counts[section_path] < max_per_section:
                diversified.append(result)
                section_counts[section_path] += 1
            elif len(diversified) < self.settings.retrieval.k_final:
                # Accetta comunque se non abbiamo abbastanza risultati
                diversified.append(result)

        return diversified

    async def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Aggiunge chunk a entrambi gli indici"""
        logger.info(f"Indicizzazione di {len(chunks)} chunk in entrambi i sistemi")

        # Estrai gli URL unici dai chunks
        unique_urls = set()
        for chunk in chunks:
            if chunk.metadata.source_url:
                unique_urls.add(chunk.metadata.source_url)

        # Elimina i vecchi chunk per ogni URL prima di aggiungere i nuovi
        if unique_urls:
            logger.info(f"Rimozione chunk esistenti per {len(unique_urls)} URL")
            for url in unique_urls:
                await self.delete_chunks_by_url(url)

        # Indicizzazione parallela
        await asyncio.gather(
            self.vector_store.add_chunks(chunks),
            self.lexical_search.add_chunks(chunks),
        )

        logger.info("Indicizzazione completata")

    async def delete_chunks_by_url(self, source_url: str) -> Tuple[int, int]:
        """
        Elimina tutti i chunk di un URL da entrambi gli indici

        Args:
            source_url: URL sorgente dei chunk da eliminare

        Returns:
            Tupla con (chunk_eliminati_vector, chunk_eliminati_lexical)
        """
        logger.info(f"Eliminazione chunk per URL: {source_url}")

        # Eliminazione parallela da entrambi gli indici
        results = await asyncio.gather(
            self.vector_store.delete_chunks_by_url(source_url),
            self.lexical_search.delete_chunks_by_url(source_url),
        )

        vector_deleted, lexical_deleted = results
        logger.info(
            f"Eliminati {vector_deleted} chunk dal vector store e {lexical_deleted} dall'indice lessicale"
        )

        return vector_deleted, lexical_deleted

    async def get_chunk_by_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        """Recupera chunk per ID (prova prima vector store)"""
        chunk = await self.vector_store.get_chunk_by_id(chunk_id)
        if not chunk:
            chunk = await self.lexical_search.get_chunk_by_id(chunk_id)
        return chunk

    async def delete_chunk(self, chunk_id: str) -> bool:
        """Elimina chunk da entrambi gli indici"""
        vector_success = await self.vector_store.delete_chunk(chunk_id)
        lexical_success = await self.lexical_search.delete_chunk(chunk_id)
        return vector_success and lexical_success

    async def get_stats(self) -> Dict[str, Any]:
        """Statistiche del sistema di retrieval"""
        vector_stats, lexical_stats = await asyncio.gather(
            self.vector_store.get_collection_stats(),
            self.lexical_search.get_index_stats(),
        )

        return {
            "vector_store": vector_stats,
            "lexical_search": lexical_stats,
            "retrieval_config": {
                "k_dense": self.settings.retrieval.k_dense,
                "k_lexical": self.settings.retrieval.k_lexical,
                "k_final": self.settings.retrieval.k_final,
                "reranker_model": self.settings.retrieval.reranker_model,
            },
        }

    async def close(self):
        """Chiude tutte le connessioni"""
        await asyncio.gather(
            self.vector_store.close(),
            self.lexical_search.close(),
        )
        logger.info("Hybrid retriever chiuso")


# Utility function per retrieval rapido
async def search_documents(
    query: str,
    top_k: int = 10,
    filters: Optional[Dict[str, Any]] = None,
) -> List[SearchResult]:
    """
    Utility per ricerca rapida

    Args:
        query: Query di ricerca
        top_k: Numero di risultati
        filters: Filtri opzionali

    Returns:
        Lista di risultati
    """
    retriever = HybridRetriever()
    await retriever.initialize()

    try:
        results = await retriever.search(query, top_k, filters)
        return results
    finally:
        await retriever.close()
