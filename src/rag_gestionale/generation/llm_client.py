"""
Client LLM per integrazione OpenAI.
Gestisce chiamate API e controllo costi.
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
from collections import defaultdict

from openai import AsyncOpenAI
from loguru import logger

from ..core.models import SearchResult, QueryType
from ..config.settings import get_settings


class LLMClient:
    """Client per OpenAI con controllo costi e rate limiting"""

    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[AsyncOpenAI] = None
        self.request_counts = defaultdict(list)  # Tracking richieste per rate limiting

    async def initialize(self):
        """Inizializza client OpenAI"""
        if not self.settings.llm.enabled or not self.settings.llm.api_key:
            logger.warning("LLM non abilitato o API key mancante")
            return

        self.client = AsyncOpenAI(
            api_key=self.settings.llm.api_key,
            timeout=self.settings.llm.timeout,
        )

        logger.info(
            f"LLM client inizializzato - Modello: {self.settings.llm.model_name}"
        )

    def is_available(self) -> bool:
        """Verifica se LLM è disponibile"""
        return (
            self.settings.llm.enabled
            and self.client is not None
            and bool(self.settings.llm.api_key)
        )

    def should_use_llm(self, query: str, query_type: QueryType) -> bool:
        """
        Determina se usare LLM basato su query complexity.

        Criteri:
        - Query lunghe (> 50 caratteri)
        - Query con domande multiple
        - Query che richiedono sintesi
        - Query di tipo GENERAL complesse
        """
        if not self.is_available():
            return False

        if not self.settings.llm.use_llm_for_complex_queries:
            return True  # Usa sempre se abilitato

        # Fattori di complessità
        complexity_score = 0

        # Lunghezza query
        if len(query) > 50:
            complexity_score += 1

        # Parole chiave per domande complesse
        complex_keywords = [
            "come",
            "perché",
            "perchè",
            "spiegare",
            "spiegami",
            "differenza",
            "confronto",
            "esempi",
            "procedura completa",
            "passo passo",
            "dettagli",
        ]

        if any(keyword in query.lower() for keyword in complex_keywords):
            complexity_score += 2

        # Query con domande multiple
        if query.count("?") > 1:
            complexity_score += 1

        # Query di tipo GENERAL tendono a essere più complesse
        if query_type == QueryType.GENERAL:
            complexity_score += 1

        # Usa LLM se score >= 2
        return complexity_score >= 2

    async def generate_response(
        self,
        query: str,
        query_type: QueryType,
        search_results: List[SearchResult],
        max_context_tokens: int = 6000,
    ) -> str:
        """
        Genera risposta usando OpenAI

        Args:
            query: Query dell'utente
            query_type: Tipo di query classificato
            search_results: Risultati della ricerca
            max_context_tokens: Token massimi per contesto

        Returns:
            Risposta generata dall'LLM
        """
        if not self.is_available():
            raise Exception("LLM non disponibile")

        # Controllo rate limiting
        if not self._check_rate_limit():
            raise Exception("Rate limit superato")

        try:
            # Costruisci prompt
            system_prompt = self._build_system_prompt(query_type)
            context = self._build_context(search_results, max_context_tokens)
            user_prompt = self._build_user_prompt(query, context)

            # Chiamata OpenAI
            response = await self.client.chat.completions.create(
                model=self.settings.llm.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.settings.llm.max_tokens,
                temperature=self.settings.llm.temperature,
                frequency_penalty=0.1,  # Riduce ripetizioni
                presence_penalty=0.1,  # Incoraggia diversità
            )

            # Tracking richiesta per rate limiting
            self._track_request()

            answer = response.choices[0].message.content.strip()
            logger.info(f"LLM risposta generata - Token: {response.usage.total_tokens}")

            return answer

        except Exception as e:
            logger.error(f"Errore LLM: {e}")
            raise

    def _build_system_prompt(self, query_type: QueryType) -> str:
        """Costruisce system prompt basato su tipo query"""
        base_prompt = """Sei un assistente esperto di software gestionale italiano specializzato in documentazione tecnica.

ISTRUZIONI FONDAMENTALI:
1. Rispondi SEMPRE in italiano
2. Usa SOLO le informazioni fornite nel contesto
3. NON inventare parametri, codici o procedure non presenti nelle fonti
4. Struttura la risposta in modo chiaro e professionale
5. Includi SEMPRE le citazioni delle fonti alla fine

FORMATO RISPOSTA:
- Introduzione breve al problema/parametro
- Spiegazione dettagliata basata sulle fonti
- Eventuali passi procedurali numerati
- Sezione "Fonti:" con elenco delle fonti citate"""

        # Prompt specifici per tipo
        type_specific = {
            QueryType.PARAMETER: """
FOCUS: Parametri e impostazioni del gestionale
- Spiega a cosa serve il parametro
- Indica dove si trova nell'interfaccia
- Descrivi i valori possibili e il comportamento
- Aggiungi avvertenze se necessario""",
            QueryType.PROCEDURE: """
FOCUS: Procedure e operazioni del gestionale
- Fornisci i passi in ordine logico e numerato
- Indica i menu e percorsi nell'interfaccia
- Specifica i prerequisiti se necessari
- Evidenzia passaggi critici o errori comuni""",
            QueryType.ERROR: """
FOCUS: Errori e risoluzione problemi
- Identifica la causa dell'errore
- Fornisci soluzioni passo-passo
- Indica come prevenire il problema
- Suggerisci controlli da effettuare""",
            QueryType.GENERAL: """
FOCUS: Informazioni generali del gestionale
- Fornisci una panoramica completa
- Organizza le informazioni in sezioni logiche
- Collega concetti correlati
- Mantieni un linguaggio tecnico ma accessibile""",
        }

        return (
            base_prompt
            + "\n\n"
            + type_specific.get(query_type, type_specific[QueryType.GENERAL])
        )

    def _build_context(
        self, search_results: List[SearchResult], max_tokens: int
    ) -> str:
        """Costruisce contesto dalle fonti limitando i token"""
        if not search_results:
            return "Nessuna fonte disponibile."

        context_parts = []
        token_count = 0
        source_counter = 1

        for result in search_results[:6]:  # Massimo 6 fonti
            # Stima token (approssimativa: 1 token ≈ 4 caratteri)
            estimated_tokens = len(result.chunk.content) // 4

            if token_count + estimated_tokens > max_tokens:
                break

            # Formato fonte
            source_text = f"""
[FONTE {source_counter}]
Titolo: {result.chunk.metadata.title}
Sezione: {" > ".join(result.chunk.metadata.breadcrumbs)}
Contenuto: {result.chunk.content}
URL: {result.chunk.metadata.source_url}
"""

            context_parts.append(source_text)
            token_count += estimated_tokens
            source_counter += 1

        return "\n".join(context_parts)

    def _build_user_prompt(self, query: str, context: str) -> str:
        """Costruisce prompt utente con query e contesto"""
        return f"""CONTESTO DOCUMENTAZIONE:
{context}

DOMANDA UTENTE:
{query}

Genera una risposta dettagliata e professionale basata esclusivamente sul contesto fornito."""

    def _check_rate_limit(self) -> bool:
        """Controlla rate limit (richieste per minuto)"""
        current_time = time.time()
        minute_ago = current_time - 60

        # Pulisci richieste vecchie
        self.request_counts["requests"] = [
            req_time
            for req_time in self.request_counts["requests"]
            if req_time > minute_ago
        ]

        # Controlla limite
        return (
            len(self.request_counts["requests"])
            < self.settings.llm.max_requests_per_minute
        )

    def _track_request(self):
        """Traccia richiesta per rate limiting"""
        self.request_counts["requests"].append(time.time())

    async def close(self):
        """Chiude client"""
        if self.client:
            await self.client.close()
        logger.info("LLM client chiuso")


# Istanza globale
_llm_client = None


async def get_llm_client() -> LLMClient:
    """Factory per client LLM"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
        await _llm_client.initialize()
    return _llm_client
