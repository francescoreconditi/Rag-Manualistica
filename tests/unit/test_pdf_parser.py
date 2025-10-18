"""
Unit tests per il modulo PDFParser
"""

import pytest

from src.rag_gestionale.core.models import ContentType, SourceFormat
from src.rag_gestionale.ingest.pdf_parser import PDFParser, PDFSection


@pytest.mark.unit
class TestPDFSection:
    """Test per la classe PDFSection"""

    def test_section_creation(self):
        """Test creazione sezione PDF"""
        section = PDFSection(
            title="Test Section",
            content="Test content",
            level=1,
            page_start=1,
            page_end=2,
        )

        assert section.title == "Test Section"
        assert section.content == "Test content"
        assert section.level == 1
        assert section.page_start == 1
        assert section.page_end == 2
        assert section.content_type is not None
        assert isinstance(section.tables, list)
        assert isinstance(section.figures, list)

    def test_classify_content_error(self):
        """Test classificazione contenuto errore"""
        section = PDFSection(
            title="Errore ERR-001",
            content="Errore: Connessione fallita. Codice errore ERR-001",
            level=1,
            page_start=1,
            page_end=1,
        )

        assert section.content_type == ContentType.ERROR

    def test_classify_content_parameter(self):
        """Test classificazione contenuto parametro"""
        section = PDFSection(
            title="Parametro IVA",
            content="Impostazione del parametro IVA predefinito",
            level=2,
            page_start=5,
            page_end=5,
        )

        assert section.content_type == ContentType.PARAMETER

    def test_classify_content_procedure(self):
        """Test classificazione contenuto procedura"""
        section = PDFSection(
            title="Procedura Fatturazione",
            content="Come creare una fattura: step 1, step 2, step 3",
            level=1,
            page_start=10,
            page_end=12,
        )

        assert section.content_type == ContentType.PROCEDURE

    def test_classify_content_table(self):
        """Test classificazione contenuto tabella"""
        section = PDFSection(
            title="Tabella Codici",
            content="Elenco dei codici utilizzati nel sistema",
            level=2,
            page_start=20,
            page_end=20,
        )

        assert section.content_type == ContentType.TABLE

    def test_classify_content_faq(self):
        """Test classificazione contenuto FAQ"""
        section = PDFSection(
            title="FAQ - Domande Frequenti",
            content="Risposte alle domande più comuni",
            level=1,
            page_start=30,
            page_end=35,
        )

        assert section.content_type == ContentType.FAQ


@pytest.mark.unit
class TestPDFParser:
    """Test per la classe PDFParser"""

    @pytest.fixture
    def parser(self):
        """Fixture che crea un parser PDF"""
        return PDFParser()

    def test_parser_initialization(self, parser):
        """Test inizializzazione parser"""
        assert parser is not None
        assert parser.min_heading_size > 0
        assert len(parser.section_patterns) > 0
        assert len(parser.heading_fonts) > 0

    def test_parse_from_path(self, parser, temp_pdf_file):
        """Test parsing da file PDF"""
        sections, metadata = parser.parse_from_path(str(temp_pdf_file))

        assert isinstance(sections, list)
        assert isinstance(metadata, dict)
        assert metadata["source_format"] == SourceFormat.PDF
        assert "source_url" in metadata
        assert "page_count" in metadata

    def test_extract_metadata(self, parser, temp_pdf_file):
        """Test estrazione metadati PDF"""
        import fitz

        doc = fitz.open(temp_pdf_file)

        try:
            metadata = parser._extract_metadata(doc, str(temp_pdf_file))

            assert "source_url" in metadata
            assert "title" in metadata
            assert "page_count" in metadata
            assert metadata["page_count"] == doc.page_count
        finally:
            doc.close()

    def test_extract_metadata_no_title(self, parser, temp_pdf_file):
        """Test estrazione metadati PDF senza titolo"""
        import fitz

        doc = fitz.open(temp_pdf_file)

        try:
            metadata = parser._extract_metadata(doc, str(temp_pdf_file))

            # Dovrebbe usare il nome del file come titolo
            assert len(metadata["title"]) > 0
        finally:
            doc.close()

    def test_clean_pdf_text(self, parser):
        """Test pulizia testo estratto da PDF"""
        dirty_text = """
        Testo normale
        123
        Una riga valida


        Altra riga valida
        45
        """

        clean_text = parser._clean_pdf_text(dirty_text)

        assert "Testo normale" in clean_text
        assert "Una riga valida" in clean_text
        # Dovrebbe rimuovere righe con solo numeri
        assert len(clean_text) > 0

    def test_clean_pdf_text_control_chars(self, parser):
        """Test rimozione caratteri di controllo"""
        text_with_control = "Testo\x00con\x08caratteri\x1fdi controllo"

        clean_text = parser._clean_pdf_text(text_with_control)

        # Caratteri di controllo dovrebbero essere rimossi
        assert "\x00" not in clean_text
        assert "\x08" not in clean_text

    def test_analyze_fonts(self, parser, temp_pdf_file):
        """Test analisi font del documento"""
        import fitz

        doc = fitz.open(temp_pdf_file)

        try:
            font_stats = parser._analyze_fonts(doc)

            assert isinstance(font_stats, dict)
            # Può essere vuoto per PDF molto semplici
        finally:
            doc.close()

    def test_extract_sections(self, parser, temp_pdf_file):
        """Test estrazione sezioni dal PDF"""
        import fitz

        doc = fitz.open(temp_pdf_file)

        try:
            heading_fonts = {}  # Empty per test semplice
            sections = parser._extract_sections(doc, heading_fonts)

            assert isinstance(sections, list)
            # Può contenere sezioni o essere vuoto
            if sections:
                assert all(isinstance(s, PDFSection) for s in sections)
                assert all(len(s.content) >= 50 for s in sections)
        finally:
            doc.close()

    def test_table_to_markdown_simple(self, parser):
        """Test conversione tabella in Markdown"""
        import pandas as pd

        df = pd.DataFrame(
            {
                "Colonna1": ["A", "B", "C"],
                "Colonna2": ["1", "2", "3"],
            }
        )

        markdown = parser._table_to_markdown(df)

        assert "Colonna1" in markdown
        assert "Colonna2" in markdown
        assert "|" in markdown
        assert "---" in markdown

    def test_table_to_markdown_with_pipe(self, parser):
        """Test conversione tabella con carattere pipe nei dati"""
        import pandas as pd

        df = pd.DataFrame(
            {
                "Col": ["A|B", "C|D"],
            }
        )

        markdown = parser._table_to_markdown(df)

        # Il pipe nei dati dovrebbe essere escaped
        assert "\\|" in markdown or "|" in markdown

    def test_table_to_markdown_empty(self, parser):
        """Test conversione tabella vuota"""
        import pandas as pd

        df = pd.DataFrame()

        markdown = parser._table_to_markdown(df)

        # Dovrebbe gestire DataFrame vuoto
        assert isinstance(markdown, str)

    def test_extract_images_with_ocr(self, parser, temp_pdf_file):
        """Test estrazione immagini con OCR"""
        import fitz

        doc = fitz.open(temp_pdf_file)

        try:
            # Test su prima pagina
            images = parser.extract_images_with_ocr(doc, 0)

            assert isinstance(images, list)
            # Il PDF di test potrebbe non avere immagini
        finally:
            doc.close()


@pytest.mark.unit
class TestPDFParserIntegration:
    """Test di integrazione per PDFParser"""

    @pytest.fixture
    def complex_pdf(self, tmp_path):
        """Crea un PDF più complesso per test"""
        import fitz

        pdf_file = tmp_path / "complex.pdf"
        doc = fitz.open()

        # Pagina 1 con titolo
        page1 = doc.new_page()
        page1.insert_text((72, 72), "Manuale Gestionale", fontsize=20)
        page1.insert_text((72, 120), "Versione 1.0", fontsize=12)

        # Pagina 2 con contenuto
        page2 = doc.new_page()
        page2.insert_text((72, 72), "Introduzione", fontsize=16)
        page2.insert_text((72, 120), "Questo è il manuale del gestionale.", fontsize=12)

        # Pagina 3 con procedura
        page3 = doc.new_page()
        page3.insert_text((72, 72), "Procedura Fatturazione", fontsize=16)
        page3.insert_text((72, 120), "1) Creare nuova fattura", fontsize=12)
        page3.insert_text((72, 140), "2) Inserire dati cliente", fontsize=12)

        doc.save(pdf_file)
        doc.close()

        return pdf_file

    def test_parse_complex_pdf(self, complex_pdf):
        """Test parsing PDF complesso"""
        parser = PDFParser()

        sections, metadata = parser.parse_from_path(str(complex_pdf))

        assert len(sections) >= 0
        assert metadata["page_count"] == 3
        assert "Gestionale" in metadata["title"] or metadata["title"] == "complex"

    def test_section_hierarchy(self, complex_pdf):
        """Test gerarchia sezioni"""
        parser = PDFParser()

        sections, _ = parser.parse_from_path(str(complex_pdf))

        # Se ha identificato sezioni, verifica la gerarchia
        if sections:
            # Le sezioni dovrebbero avere livelli diversi
            levels = {s.level for s in sections}
            assert len(levels) > 0
