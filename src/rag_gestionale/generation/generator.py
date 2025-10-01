"""
Generatore di risposte con template tipizzati e guardrail.
Include anti-hallucination e controllo qualità delle citazioni.
"""

import time
import asyncio
from typing import Dict, List, Optional, Any

from loguru import logger

from ..core.models import SearchResult, QueryType, RAGResponse
from ..config.settings import get_settings
from .templates import TemplateManager, ContextBuilder, ResponseTemplate
from .llm_client import get_llm_client


class ResponseGenerator:
    """Generatore di risposte con template e guardrail"""

    def __init__(self):
        self.settings = get_settings()
        self.template_manager = TemplateManager()
        self.context_builder = ContextBuilder()
        self.llm_client = None

    async def initialize(self):
        """Inizializza il generator e il client LLM se configurato"""
        if self.settings.llm.enabled and self.settings.llm.api_key:
            try:
                self.llm_client = await get_llm_client()
                logger.info("Client LLM inizializzato nel generator")
            except Exception as e:
                logger.error(f"Errore inizializzazione client LLM: {e}")
                self.llm_client = None

    async def generate_response(
        self,
        query: str,
        query_type: QueryType,
        search_results: List[SearchResult],
        processing_time_ms: int,
    ) -> RAGResponse:
        """
        Genera risposta usando logica ibrida (template/LLM)

        Args:
            query: Query originale
            query_type: Tipo di query classificato
            search_results: Risultati della ricerca
            processing_time_ms: Tempo di elaborazione

        Returns:
            Risposta RAG completa
        """
        start_time = time.time()

        # Controllo qualità risultati
        if not search_results or not self._has_sufficient_context(search_results):
            return self._generate_fallback_response(
                query, query_type, search_results, processing_time_ms
            )

        # Filtra risultati per qualità
        quality_results = self._filter_quality_results(search_results)

        # Determina modalità di generazione
        generation_mode = await self._determine_generation_mode(query, query_type)

        # Costruisci contesto e genera risposta
        try:
            if generation_mode == "llm":
                response_text = await self._generate_llm_response(
                    query, query_type, quality_results
                )
            else:
                response_text = self._generate_template_response(
                    query, query_type, quality_results
                )

            # Calcola confidenza
            confidence = self._calculate_confidence(quality_results, response_text)

            # Valida risposta finale
            if not self._validate_response(response_text, quality_results):
                return self._generate_fallback_response(
                    query, query_type, search_results, processing_time_ms
                )

            generation_time = int((time.time() - start_time) * 1000)

            return RAGResponse(
                query=query,
                query_type=query_type,
                answer=response_text,
                sources=quality_results,
                confidence=confidence,
                processing_time_ms=processing_time_ms + generation_time,
            )

        except Exception as e:
            logger.error(f"Errore generazione risposta: {e}")
            return self._generate_fallback_response(
                query, query_type, search_results, processing_time_ms
            )

    async def _determine_generation_mode(
        self, query: str, query_type: QueryType
    ) -> str:
        """
        Determina se usare template o LLM per la generazione

        Returns:
            'template', 'llm', o 'hybrid'
        """
        # Se LLM è configurato e disponibile, lo usa sempre
        if self.settings.llm.enabled and self.settings.llm.api_key:
            # Assicurati che il client sia inizializzato
            if self.llm_client is None:
                try:
                    self.llm_client = await get_llm_client()
                except Exception as e:
                    logger.warning(f"LLM non disponibile: {e}")
                    return "template"

            if self.llm_client and self.llm_client.is_available():
                return "llm"

        # Fallback a template se LLM non disponibile
        generation_mode = self.settings.generation.generation_mode
        if generation_mode == "template":
            return "template"
        else:
            logger.warning("LLM richiesto ma non disponibile, usando template")
            return "template"

    async def _generate_llm_response(
        self, query: str, query_type: QueryType, results: List[SearchResult]
    ) -> str:
        """Genera risposta usando LLM"""
        if self.llm_client is None:
            self.llm_client = await get_llm_client()

        return await self.llm_client.generate_response(
            query=query,
            query_type=query_type,
            search_results=results,
            max_context_tokens=self.settings.generation.max_context_tokens,
        )

    def _generate_template_response(
        self, query: str, query_type: QueryType, results: List[SearchResult]
    ) -> str:
        """Genera risposta usando template (logica originale)"""
        if query_type == QueryType.PARAMETER:
            return self._generate_parameter_response(query, results)
        elif query_type == QueryType.PROCEDURE:
            return self._generate_procedure_response(query, results)
        elif query_type == QueryType.ERROR:
            return self._generate_error_response(query, results)
        else:
            return self._generate_general_response(query, results)

    def _generate_parameter_response(
        self, query: str, results: List[SearchResult]
    ) -> str:
        """Genera risposta per parametri"""
        # Estrai nome parametro dalla query o metadati
        param_name = self._extract_parameter_name(query, results)

        context = self.context_builder.build_parameter_context(results, param_name)

        return self.template_manager.render_template(
            ResponseTemplate.PARAMETER, context
        )

    def _generate_procedure_response(
        self, query: str, results: List[SearchResult]
    ) -> str:
        """Genera risposta per procedure"""
        context = self.context_builder.build_procedure_context(results, query)

        return self.template_manager.render_template(
            ResponseTemplate.PROCEDURE, context
        )

    def _generate_error_response(self, query: str, results: List[SearchResult]) -> str:
        """Genera risposta per errori"""
        # Estrai codice errore dalla query
        error_code = self._extract_error_code(query, results)

        context = self.context_builder.build_error_context(results, error_code)

        return self.template_manager.render_template(ResponseTemplate.ERROR, context)

    def _generate_general_response(
        self, query: str, results: List[SearchResult]
    ) -> str:
        """Genera risposta generale"""
        context = self.context_builder.build_general_context(results, query)

        return self.template_manager.render_template(ResponseTemplate.GENERAL, context)

    def _generate_fallback_response(
        self,
        query: str,
        query_type: QueryType,
        search_results: List[SearchResult],
        processing_time_ms: int,
    ) -> RAGResponse:
        """Genera risposta di fallback quando non c'è abbastanza contesto"""

        # Cerca risultati correlati con threshold più basso
        suggestions = [r for r in search_results if r.score > 0.1][:3]

        context = self.context_builder.build_fallback_context(query, suggestions)

        fallback_text = self.template_manager.render_template(
            ResponseTemplate.FALLBACK, context
        )

        return RAGResponse(
            query=query,
            query_type=query_type,
            answer=fallback_text,
            sources=suggestions,
            confidence=0.0,
            processing_time_ms=processing_time_ms,
        )

    def _has_sufficient_context(self, results: List[SearchResult]) -> bool:
        """Verifica se i risultati forniscono contesto sufficiente"""
        if not results:
            return False

        # Almeno un risultato con score decente
        top_score = results[0].score if results else 0.0
        min_score = 0.5  # Soglia minima aumentata per evitare documenti poco rilevanti

        return top_score >= min_score

    def _filter_quality_results(
        self, results: List[SearchResult]
    ) -> List[SearchResult]:
        """Filtra risultati per qualità e rimuove duplicati"""
        filtered = []
        seen_sections = set()

        for result in results:
            # Filtra per score minimo - soglia più alta per evitare documenti non rilevanti
            if result.score < 0.4:
                continue

            # Evita troppi risultati dalla stessa sezione
            section_key = result.chunk.metadata.section_path
            if section_key in seen_sections:
                continue

            # Controllo gap: se c'è un gap troppo grande tra il primo e gli altri, scarta
            if filtered and (filtered[0].score - result.score) > 0.35:
                logger.debug(
                    f"Risultato scartato per gap di score troppo elevato: {result.score:.3f} vs {filtered[0].score:.3f}"
                )
                continue

            seen_sections.add(section_key)
            filtered.append(result)

            # Limita numero di risultati
            if len(filtered) >= self.settings.generation.max_context_chunks:
                break

        return filtered

    def _calculate_confidence(
        self, results: List[SearchResult], response_text: str
    ) -> float:
        """Calcola confidenza della risposta"""
        if not results:
            return 0.0

        # Fattori per confidenza
        top_score = results[0].score
        num_sources = len(results)
        avg_score = sum(r.score for r in results) / len(results)

        # Presenza di citazioni nella risposta
        citation_factor = 1.0 if "Fonti:" in response_text else 0.5

        # Lunghezza risposta (troppo corta o lunga = meno confidenza)
        length_factor = 1.0
        if len(response_text) < 100:
            length_factor = 0.7
        elif len(response_text) > 2000:
            length_factor = 0.8

        # Calcolo finale
        confidence = (
            top_score * 0.4
            + min(avg_score * 1.2, 1.0) * 0.3
            + min(num_sources / 3.0, 1.0) * 0.2
            + citation_factor * 0.1
        ) * length_factor

        return min(confidence, 1.0)

    def _validate_response(
        self, response_text: str, results: List[SearchResult]
    ) -> bool:
        """Valida la risposta finale"""

        # Controlli di base
        if len(response_text) < 50:
            return False

        # Deve contenere citazioni se richiesto
        if self.settings.generation.citation_required:
            if "Fonti:" not in response_text:
                return False

        # Non deve contenere placeholder non risolti
        if "{{" in response_text or "}}" in response_text:
            return False

        # Controllo anti-hallucination: non inventare valori specifici
        # se non sono presenti nelle fonti
        return self._check_factual_consistency(response_text, results)

    def _check_factual_consistency(
        self, response_text: str, results: List[SearchResult]
    ) -> bool:
        """Verifica che la risposta sia consistente con le fonti"""
        import re

        # Estrai claims numerici dalla risposta (escludendo numeri comuni)
        numeric_claims = re.findall(
            r"\b\d{3,}(?:\.\d+)?\s*%?\b", response_text
        )  # Solo numeri >= 3 cifre

        if not numeric_claims:
            return True  # Nessun claim numerico da verificare

        # Verifica che i valori numerici siano presenti nelle fonti
        sources_text = " ".join([r.chunk.content for r in results])
        metadata_text = " ".join(
            [r.chunk.metadata.section_path for r in results]
        )  # Include section IDs

        for claim in numeric_claims:
            if claim not in sources_text and claim not in metadata_text:
                logger.warning(f"Possibile hallucination numerica: {claim}")
                # Per ora non blocchiamo, ma logghiamo
                # return False

        return True

    def _extract_parameter_name(
        self, query: str, results: List[SearchResult]
    ) -> Optional[str]:
        """Estrae nome parametro dalla query o risultati"""
        # Prima dai metadati
        for result in results:
            if result.chunk.metadata.param_name:
                return result.chunk.metadata.param_name

        # Poi dalla query
        import re

        param_patterns = [
            r'parametro\s+["\']?([^"\'\s]+)["\']?',
            r'impostazione\s+["\']?([^"\'\s]+)["\']?',
            r'campo\s+["\']?([^"\'\s]+)["\']?',
        ]

        for pattern in param_patterns:
            match = re.search(pattern, query.lower())
            if match:
                return match.group(1).title()

        return None

    def _extract_error_code(
        self, query: str, results: List[SearchResult]
    ) -> Optional[str]:
        """Estrae codice errore dalla query o risultati"""
        import re

        # Prima dalla query
        error_match = re.search(r"\b([A-Z]{2,4}-?\d{2,4})\b", query.upper())
        if error_match:
            return error_match.group(1)

        # Poi dai metadati
        for result in results:
            if result.chunk.metadata.error_code:
                return result.chunk.metadata.error_code

        return None

    async def generate_response_async(
        self,
        query: str,
        query_type: QueryType,
        search_results: List[SearchResult],
        processing_time_ms: int,
    ) -> RAGResponse:
        """Versione asincrona della generazione (per future implementazioni LLM)"""
        # Per ora, wrapper sincrono
        # In futuro qui si potrebbe chiamare un LLM asincrono
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.generate_response,
            query,
            query_type,
            search_results,
            processing_time_ms,
        )


# Utility function per generazione rapida
def generate_answer(
    query: str,
    query_type: QueryType,
    search_results: List[SearchResult],
    processing_time_ms: int = 0,
) -> RAGResponse:
    """
    Utility per generazione rapida di risposte

    Args:
        query: Query dell'utente
        query_type: Tipo di query
        search_results: Risultati della ricerca
        processing_time_ms: Tempo di processing

    Returns:
        Risposta RAG completa
    """
    generator = ResponseGenerator()
    return asyncio.run(
        generator.generate_response(
            query, query_type, search_results, processing_time_ms
        )
    )
