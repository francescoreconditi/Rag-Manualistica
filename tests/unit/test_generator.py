"""
Unit tests per il modulo ResponseGenerator
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag_gestionale.core.models import QueryType, RAGResponse
from src.rag_gestionale.generation.generator import ResponseGenerator


@pytest.mark.unit
class TestResponseGenerator:
    """Test per ResponseGenerator"""

    @pytest.fixture
    async def generator(self, mock_llm_client):
        """Fixture che crea un ResponseGenerator"""
        with patch(
            "src.rag_gestionale.generation.generator.get_llm_client"
        ) as mock_get_client:
            mock_get_client.return_value = mock_llm_client

            gen = ResponseGenerator()
            await gen.initialize()
            return gen

    @pytest.mark.asyncio
    async def test_initialization(self, generator):
        """Test inizializzazione generator"""
        assert generator is not None
        assert generator.template_manager is not None
        assert generator.context_builder is not None

    @pytest.mark.asyncio
    async def test_generate_response_with_results(
        self, generator, sample_search_results
    ):
        """Test generazione risposta con risultati validi"""
        query = "come creare una fattura"
        query_type = QueryType.PROCEDURE

        response = await generator.generate_response(
            query, query_type, sample_search_results, processing_time_ms=100
        )

        assert isinstance(response, RAGResponse)
        assert response.query == query
        assert response.query_type == query_type
        assert len(response.answer) > 0
        assert response.confidence > 0

    @pytest.mark.asyncio
    async def test_generate_response_no_results(self, generator):
        """Test generazione risposta senza risultati"""
        query = "query senza risultati"
        query_type = QueryType.GENERAL

        response = await generator.generate_response(
            query, query_type, [], processing_time_ms=50
        )

        assert isinstance(response, RAGResponse)
        assert response.confidence == 0.0
        # Dovrebbe essere una risposta fallback

    @pytest.mark.asyncio
    async def test_generate_response_low_score(self, generator, sample_search_results):
        """Test generazione risposta con score basso"""
        query = "test query"
        query_type = QueryType.GENERAL

        # Imposta score molto bassi
        for result in sample_search_results:
            result.score = 0.1

        response = await generator.generate_response(
            query, query_type, sample_search_results, processing_time_ms=100
        )

        assert isinstance(response, RAGResponse)
        # Potrebbe essere fallback per score troppo basso

    @pytest.mark.asyncio
    async def test_generate_parameter_response(self, generator, sample_parameter_chunk):
        """Test generazione risposta per parametro"""
        from src.rag_gestionale.core.models import SearchResult

        query = "parametro IVA"
        results = [
            SearchResult(
                chunk=sample_parameter_chunk,
                score=0.9,
                explanation="Match",
                images=[],
            )
        ]

        response = generator._generate_template_response(
            query, QueryType.PARAMETER, results
        )

        assert len(response) > 0
        assert "IVA" in response or "parametro" in response.lower()

    @pytest.mark.asyncio
    async def test_generate_procedure_response(self, generator, sample_procedure_chunk):
        """Test generazione risposta per procedura"""
        from src.rag_gestionale.core.models import SearchResult

        query = "come creare fattura"
        results = [
            SearchResult(
                chunk=sample_procedure_chunk,
                score=0.9,
                explanation="Match",
                images=[],
            )
        ]

        response = generator._generate_template_response(
            query, QueryType.PROCEDURE, results
        )

        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_generate_error_response(self, generator, sample_error_chunk):
        """Test generazione risposta per errore"""
        from src.rag_gestionale.core.models import SearchResult

        query = "errore ERR-001"
        results = [
            SearchResult(
                chunk=sample_error_chunk, score=0.9, explanation="Match", images=[]
            )
        ]

        response = generator._generate_template_response(
            query, QueryType.ERROR, results
        )

        assert len(response) > 0
        assert "ERR-001" in response or "errore" in response.lower()

    @pytest.mark.asyncio
    async def test_generate_general_response(self, generator, sample_search_results):
        """Test generazione risposta generale"""
        query = "informazioni sul sistema"

        response = generator._generate_template_response(
            query, QueryType.GENERAL, sample_search_results
        )

        assert len(response) > 0

    def test_has_sufficient_context_good(self, generator, sample_search_results):
        """Test verifica contesto sufficiente con buoni risultati"""
        # Score alto
        for result in sample_search_results:
            result.score = 0.8

        has_context = generator._has_sufficient_context(sample_search_results)

        assert has_context is True

    def test_has_sufficient_context_poor(self, generator, sample_search_results):
        """Test verifica contesto insufficiente"""
        # Score troppo basso
        for result in sample_search_results:
            result.score = 0.2

        has_context = generator._has_sufficient_context(sample_search_results)

        assert has_context is False

    def test_has_sufficient_context_empty(self, generator):
        """Test verifica contesto con lista vuota"""
        has_context = generator._has_sufficient_context([])

        assert has_context is False

    def test_filter_quality_results(self, generator, sample_search_results):
        """Test filtro risultati per qualità"""
        filtered = generator._filter_quality_results(sample_search_results)

        assert len(filtered) <= len(sample_search_results)
        assert all(r.score >= 0.4 for r in filtered if not r.images)

    def test_filter_quality_results_with_gap(self, generator, sample_search_results):
        """Test filtro con gap di score"""
        # Primo risultato molto alto, altri bassi
        sample_search_results[0].score = 0.95
        for i in range(1, len(sample_search_results)):
            sample_search_results[i].score = 0.4

        filtered = generator._filter_quality_results(sample_search_results)

        # Dovrebbe scartare risultati con gap troppo grande
        assert len(filtered) < len(sample_search_results)

    def test_filter_quality_results_preserves_images(
        self, generator, sample_search_results
    ):
        """Test che i risultati con immagini non vengano scartati"""
        # Aggiungi immagini a un risultato con score basso
        sample_search_results[2].score = 0.2
        sample_search_results[2].images = [
            {"id": "img_001", "url": "http://test.com/img.png"}
        ]

        filtered = generator._filter_quality_results(sample_search_results)

        # Il risultato con immagini dovrebbe essere preservato
        has_image_result = any(len(r.images) > 0 for r in filtered)
        assert has_image_result

    def test_calculate_confidence_high(self, generator, sample_search_results):
        """Test calcolo confidenza alta"""
        # Score alti
        for result in sample_search_results:
            result.score = 0.9

        response_text = "Risposta dettagliata con Fonti: [1][2][3]"

        confidence = generator._calculate_confidence(
            sample_search_results, response_text
        )

        assert 0.7 <= confidence <= 1.0

    def test_calculate_confidence_low(self, generator, sample_search_results):
        """Test calcolo confidenza bassa"""
        # Score bassi e pochi risultati
        sample_search_results = sample_search_results[:1]
        sample_search_results[0].score = 0.5

        response_text = "Risposta breve"

        confidence = generator._calculate_confidence(
            sample_search_results, response_text
        )

        assert confidence < 0.7

    def test_validate_response_good(self, generator, sample_search_results):
        """Test validazione risposta valida"""
        response = "Questa è una risposta valida e dettagliata.\n\nFonti: [1] Test"

        is_valid = generator._validate_response(response, sample_search_results)

        assert is_valid is True

    def test_validate_response_too_short(self, generator, sample_search_results):
        """Test validazione risposta troppo corta"""
        response = "Breve"

        is_valid = generator._validate_response(response, sample_search_results)

        assert is_valid is False

    def test_validate_response_no_citations(self, generator, sample_search_results):
        """Test validazione risposta senza citazioni"""
        # Forza citation_required = True
        generator.settings.generation.citation_required = True

        response = "Risposta senza citazioni"

        is_valid = generator._validate_response(response, sample_search_results)

        assert is_valid is False

    def test_validate_response_with_placeholders(
        self, generator, sample_search_results
    ):
        """Test validazione risposta con placeholder non risolti"""
        response = "Risposta con {{placeholder}} non risolto\n\nFonti: [1]"

        is_valid = generator._validate_response(response, sample_search_results)

        assert is_valid is False

    def test_check_factual_consistency(self, generator, sample_search_results):
        """Test controllo consistenza fattuale"""
        # Risposta senza claim numerici specifici
        response = "Il sistema permette di gestire le fatture"

        is_consistent = generator._check_factual_consistency(
            response, sample_search_results
        )

        assert is_consistent is True

    def test_extract_parameter_name_from_metadata(
        self, generator, sample_parameter_chunk
    ):
        """Test estrazione nome parametro dai metadati"""
        from src.rag_gestionale.core.models import SearchResult

        results = [
            SearchResult(
                chunk=sample_parameter_chunk,
                score=0.9,
                explanation="Match",
                images=[],
            )
        ]

        param_name = generator._extract_parameter_name("test query", results)

        assert param_name == "IVA_DEFAULT"

    def test_extract_parameter_name_from_query(self, generator, sample_search_results):
        """Test estrazione nome parametro dalla query"""
        query = 'parametro "IVA_PREDEFINITA" configurazione'

        param_name = generator._extract_parameter_name(query, sample_search_results)

        # Dovrebbe estrarre il nome dalla query
        assert param_name is not None

    def test_extract_error_code_from_query(self, generator, sample_search_results):
        """Test estrazione codice errore dalla query"""
        query = "errore ERR-001 nel sistema"

        error_code = generator._extract_error_code(query, sample_search_results)

        assert error_code == "ERR-001"

    def test_extract_error_code_from_metadata(self, generator, sample_error_chunk):
        """Test estrazione codice errore dai metadati"""
        from src.rag_gestionale.core.models import SearchResult

        results = [
            SearchResult(
                chunk=sample_error_chunk, score=0.9, explanation="Match", images=[]
            )
        ]

        error_code = generator._extract_error_code("errore sistema", results)

        assert error_code == "ERR-001"

    @pytest.mark.asyncio
    async def test_determine_generation_mode_llm_available(self, generator):
        """Test determinazione modalità con LLM disponibile"""
        mode = await generator._determine_generation_mode(
            "test query", QueryType.GENERAL
        )

        # Se LLM è mockato e disponibile
        if generator.llm_client and generator.llm_client.is_available():
            assert mode == "llm"

    @pytest.mark.asyncio
    async def test_generate_fallback_response(self, generator, sample_search_results):
        """Test generazione risposta fallback"""
        query = "query senza contesto"

        response = generator._generate_fallback_response(
            query, QueryType.GENERAL, sample_search_results, processing_time_ms=100
        )

        assert isinstance(response, RAGResponse)
        assert response.confidence == 0.0
        assert len(response.answer) > 0


@pytest.mark.unit
@pytest.mark.requires_llm
class TestResponseGeneratorWithLLM:
    """Test per ResponseGenerator con LLM attivo"""

    @pytest.fixture
    async def generator_with_llm(self, mock_llm_client):
        """Fixture con LLM mockato attivo"""
        with patch(
            "src.rag_gestionale.generation.generator.get_llm_client"
        ) as mock_get_client:
            mock_get_client.return_value = mock_llm_client
            mock_llm_client.is_available.return_value = True

            gen = ResponseGenerator()
            gen.llm_client = mock_llm_client
            return gen

    @pytest.mark.asyncio
    async def test_generate_llm_response(
        self, generator_with_llm, sample_search_results
    ):
        """Test generazione risposta con LLM"""
        query = "test query"

        response = await generator_with_llm._generate_llm_response(
            query, QueryType.GENERAL, sample_search_results
        )

        assert len(response) > 0
        assert generator_with_llm.llm_client.generate_response.called
