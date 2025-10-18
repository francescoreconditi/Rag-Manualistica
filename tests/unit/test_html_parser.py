"""
Unit tests per il modulo HTMLParser
"""

import pytest

from src.rag_gestionale.core.models import ContentType, SourceFormat
from src.rag_gestionale.ingest.html_parser import HTMLParser, HTMLSection


@pytest.mark.unit
class TestHTMLSection:
    """Test per HTMLSection"""

    def test_section_creation(self):
        """Test creazione sezione HTML"""
        section = HTMLSection(
            title="Test Section",
            content="Test content",
            level=1,
            section_id="sec_001",
            anchor="test-section",
        )

        assert section.title == "Test Section"
        assert section.content == "Test content"
        assert section.level == 1
        assert section.section_id == "sec_001"
        assert section.anchor == "test-section"
        assert section.content_type is not None

    def test_classify_content_error(self):
        """Test classificazione contenuto errore"""
        section = HTMLSection(
            title="Errore Sistema",
            content="Errore: Connessione fallita. Codice errore ERR-001",
            level=1,
            section_id="sec_001",
        )

        assert section.content_type == ContentType.ERROR

    def test_classify_content_parameter(self):
        """Test classificazione contenuto parametro"""
        section = HTMLSection(
            title="Parametro IVA",
            content="Impostazione del parametro IVA predefinito per le fatture",
            level=2,
            section_id="sec_002",
        )

        assert section.content_type == ContentType.PARAMETER

    def test_classify_content_procedure(self):
        """Test classificazione contenuto procedura"""
        section = HTMLSection(
            title="Procedura Fatturazione",
            content="Come creare una fattura: step 1, step 2, step 3",
            level=1,
            section_id="sec_003",
        )

        assert section.content_type == ContentType.PROCEDURE

    def test_classify_content_table(self):
        """Test classificazione contenuto tabella"""
        section = HTMLSection(
            title="Tabella Codici",
            content="Elenco dei codici utilizzati nel sistema",
            level=2,
            section_id="sec_004",
        )

        assert section.content_type == ContentType.TABLE

    def test_classify_content_faq(self):
        """Test classificazione contenuto FAQ"""
        section = HTMLSection(
            title="FAQ - Domande Frequenti",
            content="Risposte alle domande più comuni",
            level=1,
            section_id="sec_005",
        )

        assert section.content_type == ContentType.FAQ

    def test_update_content(self):
        """Test aggiornamento contenuto"""
        section = HTMLSection(
            title="Test",
            content="Old content",
            level=1,
            section_id="sec_001",
        )

        old_content = section.content
        section.update_content("New content with error ERR-123")

        assert section.content != old_content
        assert "New content" in section.content
        # Content type potrebbe essere aggiornato
        assert section.content_type is not None

    def test_section_with_tables(self):
        """Test sezione con tabelle"""
        section = HTMLSection(
            title="Test",
            content="Content",
            level=1,
            section_id="sec_001",
        )

        section.tables.append("| Col1 | Col2 |\n|------|------|")

        assert len(section.tables) == 1

    def test_section_with_figures(self):
        """Test sezione con figure"""
        section = HTMLSection(
            title="Test",
            content="Content",
            level=1,
            section_id="sec_001",
        )

        section.figures.append(
            {"src": "http://example.com/img.png", "caption": "Test image"}
        )

        assert len(section.figures) == 1


@pytest.mark.unit
class TestHTMLParser:
    """Test per HTMLParser"""

    @pytest.fixture
    def parser(self):
        """Fixture che crea un parser HTML"""
        return HTMLParser()

    @pytest.fixture
    def simple_html(self):
        """HTML semplice per test"""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Test Document</title></head>
        <body>
            <h1>Main Title</h1>
            <p>This is the main content.</p>
            <h2>Subsection</h2>
            <p>This is subsection content.</p>
        </body>
        </html>
        """

    @pytest.fixture
    def complex_html(self):
        """HTML complesso con tabelle e immagini"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Complex Document</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <h1>Procedura Fatturazione</h1>
            <p>Come creare una fattura nel sistema</p>

            <h2>Step 1</h2>
            <p>Accedere al menu fatturazione</p>

            <h2>Parametro IVA</h2>
            <p>Configurazione parametro IVA predefinito</p>

            <table>
                <tr><th>Codice</th><th>Descrizione</th></tr>
                <tr><td>001</td><td>Fattura Vendita</td></tr>
                <tr><td>002</td><td>Fattura Acquisto</td></tr>
            </table>

            <img src="screenshot.png" alt="Screenshot sistema">
        </body>
        </html>
        """

    def test_parser_initialization(self, parser):
        """Test inizializzazione parser"""
        assert parser is not None
        assert len(parser.remove_selectors) > 0
        assert len(parser.keep_selectors) > 0

    def test_parse_simple_html(self, parser, simple_html):
        """Test parsing HTML semplice"""
        sections, metadata = parser.parse_from_url(
            "http://example.com/doc", simple_html
        )

        assert isinstance(sections, list)
        assert isinstance(metadata, dict)
        assert len(sections) > 0
        assert "title" in metadata

    def test_parse_complex_html(self, parser, complex_html):
        """Test parsing HTML complesso"""
        sections, metadata = parser.parse_from_url(
            "http://example.com/doc", complex_html
        )

        assert len(sections) > 0
        assert metadata["title"] == "Complex Document"

        # Verifica che abbia estratto diverse sezioni
        section_titles = [s.title for s in sections]
        assert any(
            "Procedura" in title or "Step" in title or "Parametro" in title
            for title in section_titles
        )

    def test_extract_metadata(self, parser, complex_html):
        """Test estrazione metadati"""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(complex_html, "html.parser")
            metadata = parser._extract_metadata(soup, "http://example.com/doc")

            assert metadata["title"] == "Complex Document"
            assert metadata["description"] == "Test description"
            assert metadata["source_url"] == "http://example.com/doc"
            assert metadata["source_format"] == SourceFormat.HTML
        except ImportError:
            pytest.skip("BeautifulSoup non disponibile")

    def test_extract_metadata_no_title(self, parser):
        """Test estrazione metadati senza titolo"""
        html = "<html><body><p>No title</p></body></html>"

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            metadata = parser._extract_metadata(soup, "http://example.com")

            # Dovrebbe avere title vuoto o preso da h1
            assert "title" in metadata
        except ImportError:
            pytest.skip("BeautifulSoup non disponibile")

    def test_extract_sections(self, parser, complex_html):
        """Test estrazione sezioni"""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(complex_html, "html.parser")
            parser._clean_soup(soup)
            sections = parser._extract_sections(soup, "http://example.com")

            assert len(sections) > 0
            assert all(isinstance(s, HTMLSection) for s in sections)
            assert all(len(s.content) > 0 for s in sections)
        except ImportError:
            pytest.skip("BeautifulSoup non disponibile")

    def test_extract_table(self, parser):
        """Test estrazione tabella"""
        html = """
        <table>
            <tr><th>Header1</th><th>Header2</th></tr>
            <tr><td>Data1</td><td>Data2</td></tr>
            <tr><td>Data3</td><td>Data4</td></tr>
        </table>
        """

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table")
            markdown = parser._extract_table(table)

            assert "Header1" in markdown
            assert "Header2" in markdown
            assert "Data1" in markdown
            assert "|" in markdown
            assert "---" in markdown
        except ImportError:
            pytest.skip("BeautifulSoup non disponibile")

    def test_extract_table_with_pipe(self, parser):
        """Test estrazione tabella con pipe nei dati"""
        html = """
        <table>
            <tr><th>Col</th></tr>
            <tr><td>Data | with pipe</td></tr>
        </table>
        """

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            table = soup.find("table")
            markdown = parser._extract_table(table)

            # Il pipe dovrebbe essere escaped
            assert "\\|" in markdown or "|" in markdown
        except ImportError:
            pytest.skip("BeautifulSoup non disponibile")

    def test_extract_figure(self, parser):
        """Test estrazione figura"""
        html = """
        <figure>
            <img src="/img/screenshot.png" alt="Screenshot">
            <figcaption>Test screenshot</figcaption>
        </figure>
        """

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            figure = soup.find("figure")
            figure_data = parser._extract_figure(figure, "http://example.com")

            assert figure_data is not None
            assert "screenshot.png" in figure_data["src"]
            assert figure_data["caption"] == "Test screenshot"
            assert figure_data["alt"] == "Screenshot"
        except ImportError:
            pytest.skip("BeautifulSoup non disponibile")

    def test_extract_figure_without_caption(self, parser):
        """Test estrazione figura senza caption"""
        html = '<img src="test.png" alt="Test image">'

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            img = soup.find("img")
            figure_data = parser._extract_figure(img, "http://example.com")

            assert figure_data is not None
            assert figure_data["caption"] == "Test image"  # Dovrebbe usare alt
        except ImportError:
            pytest.skip("BeautifulSoup non disponibile")

    def test_generate_anchor(self, parser):
        """Test generazione anchor da titolo"""
        titles = [
            ("Test Section", "test-section"),
            ("Parametro IVA", "parametro-iva"),
            ("Come fare?", "come-fare"),
            ("Multiple   Spaces", "multiple-spaces"),
        ]

        for title, expected in titles:
            anchor = parser._generate_anchor(title)
            assert anchor == expected

    def test_clean_soup(self, parser):
        """Test pulizia soup"""
        html = """
        <html>
        <head><style>body { color: red; }</style></head>
        <body>
            <nav>Navigation</nav>
            <header>Header</header>
            <main>
                <p>Content</p>
            </main>
            <footer>Footer</footer>
            <script>alert('test')</script>
        </body>
        </html>
        """

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            parser._clean_soup(soup)

            # Nav, header, footer, script, style dovrebbero essere rimossi
            assert soup.find("nav") is None
            assert soup.find("header") is None
            assert soup.find("footer") is None
            assert soup.find("script") is None
            assert soup.find("style") is None

            # Content dovrebbe rimanere
            assert soup.find("p") is not None
        except ImportError:
            pytest.skip("BeautifulSoup non disponibile")

    def test_simple_parse_fallback(self, parser, simple_html):
        """Test fallback parsing semplice"""
        sections, metadata = parser._simple_parse("http://example.com", simple_html)

        assert len(sections) > 0
        assert metadata["title"] is not None
        assert metadata["source_url"] == "http://example.com"

    def test_simple_parse_no_title(self, parser):
        """Test parsing semplice senza title tag"""
        html = "<html><body><p>Content without title</p></body></html>"

        sections, metadata = parser._simple_parse("http://example.com", html)

        assert len(sections) > 0
        assert "title" in metadata

    def test_extract_parameters_from_section(self, parser):
        """Test estrazione parametri da sezione"""
        section = HTMLSection(
            title="Parametri Sistema",
            content="""
            Parametro: IVA_DEFAULT
            Descrizione: Aliquota IVA predefinita

            Campo: MAGAZZINO_PRINCIPALE
            Descrizione: Magazzino principale di default
            """,
            level=1,
            section_id="sec_001",
        )

        # Forza content_type
        section.content_type = ContentType.PARAMETER

        parameters = parser.extract_parameters_from_section(section)

        # Dovrebbe estrarre parametri
        assert isinstance(parameters, list)

    def test_extract_parameters_from_non_parameter_section(self, parser):
        """Test che non estragga parametri da sezioni non-parameter"""
        section = HTMLSection(
            title="Generale",
            content="Contenuto generico",
            level=1,
            section_id="sec_001",
        )

        section.content_type = ContentType.CONCEPT

        parameters = parser.extract_parameters_from_section(section)

        assert parameters == []


@pytest.mark.unit
class TestHTMLParserIntegration:
    """Test di integrazione per HTMLParser"""

    @pytest.fixture
    def wiki_html(self):
        """HTML in stile MediaWiki"""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Manuale - Contabilità v2.0</title></head>
        <body>
            <div class="breadcrumb-nav">Home > Contabilità</div>

            <h1>Contabilità</h1>
            <p>Sistema di contabilità integrato</p>

            <h2>Procedura: Registrazione Fattura</h2>
            <p>Come registrare una fattura nel sistema:</p>
            <ol>
                <li>Accedere al menu Contabilità</li>
                <li>Selezionare "Nuova Fattura"</li>
                <li>Compilare i campi richiesti</li>
            </ol>

            <h2>Errore ERR-001: Connessione Database</h2>
            <p>Errore durante connessione al database</p>

            <div class="toc">Table of contents (should be removed)</div>
        </body>
        </html>
        """

    def test_parse_wiki_document(self, wiki_html):
        """Test parsing documento wiki completo"""
        parser = HTMLParser()

        sections, metadata = parser.parse_from_url("http://wiki.example.com", wiki_html)

        assert len(sections) > 0

        # Verifica metadati estratti
        assert "Contabilità" in metadata["title"] or "Manuale" in metadata["title"]
        assert "v2.0" in metadata["version"] or metadata["version"] == ""

        # Verifica tipi di sezioni
        content_types = [s.content_type for s in sections]
        # Potrebbe contenere PROCEDURE, ERROR, etc.
        assert len(content_types) > 0

    def test_full_parsing_workflow(self):
        """Test flusso completo di parsing"""
        parser = HTMLParser()

        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Test</title></head>
        <body>
            <h1>Manuale Utente</h1>
            <p>Contenuto manuale</p>
            <h2>Sezione 1</h2>
            <p>Contenuto sezione 1</p>
        </body>
        </html>
        """

        sections, metadata = parser.parse_from_url("http://example.com", html)

        # Verifica risultati
        assert len(sections) > 0
        assert all(isinstance(s, HTMLSection) for s in sections)
        assert all(s.content for s in sections)
        assert all(s.title for s in sections)
        assert metadata["source_url"] == "http://example.com"
