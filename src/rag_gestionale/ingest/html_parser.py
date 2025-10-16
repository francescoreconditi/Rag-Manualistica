"""
Parser HTML specializzato per manuali di gestionali.
Ottimizzato per estrarre struttura gerarchica, tabelle e metadati.
"""

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import html

try:
    from bs4 import BeautifulSoup, Tag

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    BeautifulSoup = None
    Tag = None

from trafilatura import extract
from trafilatura.settings import use_config

from ..core.models import ContentType, SourceFormat
from ..core.utils import (
    clean_html_tags,
    extract_breadcrumbs,
    extract_error_codes,
    extract_ui_path_from_text,
    normalize_text,
)


class HTMLSection:
    """Rappresenta una sezione del documento HTML"""

    def __init__(
        self,
        title: str,
        content: str,
        level: int,
        section_id: str,
        anchor: Optional[str] = None,
    ):
        self.title = title
        self.content = content
        self.level = level
        self.section_id = section_id
        self.anchor = anchor
        self.tables: List[str] = []
        self.figures: List[Dict[str, str]] = []

        # Inizializzazione sicura degli attributi
        self.content_type = ContentType.CONCEPT
        self.ui_path = None
        self.error_codes = []

        # Prova ad aggiornare con valori reali
        try:
            self._update_derived_attributes()
        except Exception:
            pass  # Mantieni valori di default

    def _update_derived_attributes(self):
        """Aggiorna attributi derivati dal contenuto"""
        try:
            self.content_type = self._classify_content()
            self.ui_path = extract_ui_path_from_text(self.content)
            self.error_codes = extract_error_codes(self.content)
        except Exception as e:
            # Fallback sicuro se qualcosa va storto
            self.content_type = ContentType.CONCEPT
            self.ui_path = None
            self.error_codes = []

    def update_content(self, content: str):
        """Aggiorna il contenuto e ricalcola attributi derivati"""
        self.content = content
        self._update_derived_attributes()

    def _classify_content(self) -> ContentType:
        """Classifica il tipo di contenuto della sezione"""
        content_lower = self.content.lower()
        title_lower = self.title.lower()

        # Parole chiave per classificazione
        error_patterns = ["errore", "error", "codice", "avviso", "warning"]
        param_patterns = [
            "parametro",
            "impostazione",
            "configurazione",
            "settaggio",
            "opzione",
        ]
        procedure_patterns = [
            "procedura",
            "come",
            "step",
            "passo",
            "istruzione",
            "guida",
        ]
        table_patterns = ["tabella", "elenco", "lista"]

        # Codici errore
        if (
            any(pattern in content_lower for pattern in error_patterns)
            or self.error_codes
        ):
            return ContentType.ERROR

        # Parametri
        if any(pattern in title_lower for pattern in param_patterns):
            return ContentType.PARAMETER

        # Procedure
        if any(pattern in content_lower for pattern in procedure_patterns):
            return ContentType.PROCEDURE

        # Tabelle
        if any(pattern in title_lower for pattern in table_patterns):
            return ContentType.TABLE

        # FAQ
        if "faq" in title_lower or "domande" in title_lower:
            return ContentType.FAQ

        return ContentType.CONCEPT


class HTMLParser:
    """Parser HTML per manuali di gestionali"""

    def __init__(self):
        # Configurazione trafilatura per contenuto tecnico
        self.config = use_config()
        self.config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")
        self.config.set("DEFAULT", "MIN_EXTRACTED_SIZE", "100")

        # Selettori da rimuovere (navigazione, cookie, etc.)
        self.remove_selectors = [
            "nav",
            "aside",
            "footer",
            "header",
            ".navigation",
            ".nav",
            ".sidebar",
            ".cookie",
            ".banner",
            ".advertisement",
            ".breadcrumb-nav",
            ".toc",
            "#toc",
            ".print-only",
            ".no-print",
        ]

        # Selettori da mantenere
        self.keep_selectors = [
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "li",
            "ol",
            "ul",
            "table",
            ".note",
            ".warning",
            ".attention",
            ".code",
            "pre",
            "code",
            "img",
            "figure",
            "figcaption",
        ]

    def parse_from_url(
        self, url: str, html_content: str
    ) -> Tuple[List[HTMLSection], Dict]:
        """
        Parse HTML da URL

        Args:
            url: URL del documento
            html_content: Contenuto HTML

        Returns:
            Tuple di (sezioni, metadati)
        """
        if not HAS_BS4:
            # Fallback semplice senza BeautifulSoup
            return self._simple_parse(url, html_content)

        # Parse completo con BeautifulSoup
        try:
            # Estrazione con trafilatura per contenuto pulito
            extracted_text = extract(
                html_content,
                config=self.config,
                include_comments=False,
                include_tables=True,
            )

            # Parse dettagliato con BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")

            # Rimuovi elementi indesiderati
            self._clean_soup(soup)

            # Estrai metadati generali
            metadata = self._extract_metadata(soup, url)

            # Estrai sezioni strutturate
            sections = self._extract_sections(soup, url)

            return sections, metadata
        except Exception:
            # Fallback in caso di errore
            return self._simple_parse(url, html_content)

    def _simple_parse(
        self, url: str, html_content: str
    ) -> Tuple[List[HTMLSection], Dict]:
        """Parser semplificato senza BeautifulSoup"""
        # Usa trafilatura per estrarre contenuto
        try:
            extracted_text = extract(
                html_content,
                config=self.config,
                include_comments=False,
                include_tables=True,
            )
        except Exception:
            # Rimuovi tag HTML in modo grezzo
            extracted_text = re.sub(r"<[^>]+>", "", html_content)

        if not extracted_text:
            extracted_text = "Contenuto non estratto"

        # Metadati semplici
        title_match = re.search(
            r"<title[^>]*>([^<]+)</title>", html_content, re.IGNORECASE
        )
        title = title_match.group(1) if title_match else "Documento"

        metadata = {
            "title": html.unescape(title.strip()),
            "source_url": url,
            "version": "1.0",
            "module": "Generale",
        }

        # Crea una singola sezione con tutto il contenuto
        section = HTMLSection(
            title=metadata["title"],
            content=extracted_text[:5000],  # Limita lunghezza
            level=1,
            section_id="main_content",
            anchor="top",
        )

        return [section], metadata

    def _clean_soup(self, soup) -> None:
        """Pulisce il soup rimuovendo elementi indesiderati"""
        for selector in self.remove_selectors:
            for element in soup.select(selector):
                element.decompose()

        # Rimuovi attributi di stile e script
        for tag in soup.find_all():
            if tag.name in ["script", "style"]:
                tag.decompose()
                continue

            # Mantieni solo alcuni attributi utili
            if hasattr(tag, "attrs"):
                keep_attrs = ["id", "class", "href", "src", "alt", "title"]
                tag.attrs = {k: v for k, v in tag.attrs.items() if k in keep_attrs}

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Estrae metadati dal documento"""
        metadata = {
            "source_url": url,
            "source_format": SourceFormat.HTML,
            "title": "",
            "description": "",
            "module": "",
            "version": "",
            "last_modified": None,
        }

        # Titolo
        title_tag = soup.find("title") or soup.find("h1")
        if title_tag:
            metadata["title"] = clean_html_tags(title_tag.get_text()).strip()

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            metadata["description"] = meta_desc["content"].strip()

        # Cerca modulo nel titolo o breadcrumb
        if metadata["title"]:
            module_match = re.search(
                r"(Contabilità|Fatturazione|Magazzino|HR|Desktop\w+)",
                metadata["title"],
                re.IGNORECASE,
            )
            if module_match:
                metadata["module"] = module_match.group(1)

        # Cerca versione
        version_match = re.search(r"v?(\d+\.\d+(?:\.\d+)?)", metadata["title"] or "")
        if version_match:
            metadata["version"] = version_match.group(1)

        return metadata

    def _extract_sections(
        self, soup: BeautifulSoup, base_url: str
    ) -> List[HTMLSection]:
        """Estrae sezioni dal documento con gerarchia"""
        sections = []
        current_section = None
        section_counter = 0

        # Trova tutti gli heading e il contenuto associato
        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            level = int(element.name[1])
            title = clean_html_tags(element.get_text()).strip()

            if not title:
                continue

            # Finalizza sezione precedente
            if current_section:
                sections.append(current_section)

            # Crea nuova sezione
            section_counter += 1
            section_id = f"section_{section_counter:03d}"
            anchor = element.get("id") or self._generate_anchor(title)

            current_section = HTMLSection(
                title=title,
                content="",
                level=level,
                section_id=section_id,
                anchor=anchor,
            )

            # Raccogli contenuto fino al prossimo heading dello stesso livello o superiore
            content_elements = []
            next_element = element.next_sibling

            while next_element:
                if hasattr(next_element, "name") and next_element.name in [
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                ]:
                    next_level = int(next_element.name[1])
                    if next_level <= level:
                        break

                if hasattr(next_element, "get_text"):
                    # Gestione speciale per tabelle
                    if next_element.name == "table":
                        table_text = self._extract_table(next_element)
                        if table_text:
                            current_section.tables.append(table_text)
                            content_elements.append(f"[Tabella]\n{table_text}")

                    # Gestione immagini con caption
                    elif next_element.name in ["img", "figure"]:
                        figure_data = self._extract_figure(next_element, base_url)
                        if figure_data:
                            current_section.figures.append(figure_data)
                            content_elements.append(
                                f"[Figura: {figure_data['caption']}]"
                            )

                    else:
                        # Cerca immagini dentro questo elemento (per MediaWiki con <div class="thumb">)
                        if hasattr(next_element, "find_all"):
                            imgs_in_element = next_element.find_all("img")
                            for img_tag in imgs_in_element:
                                figure_data = self._extract_figure(img_tag, base_url)
                                if figure_data:
                                    current_section.figures.append(figure_data)
                                    content_elements.append(
                                        f"[Figura: {figure_data['caption']}]"
                                    )

                        text = clean_html_tags(next_element.get_text()).strip()
                        if text:
                            content_elements.append(text)

                next_element = next_element.next_sibling

            # Assembla contenuto
            if content_elements:
                current_section.update_content(
                    normalize_text("\n\n".join(content_elements))
                )

        # Aggiungi ultima sezione
        if current_section:
            sections.append(current_section)

        return [
            s for s in sections if len(s.content) > 50
        ]  # Filtra sezioni troppo corte

    def _extract_table(self, table_element: Tag) -> str:
        """Estrae contenuto tabella in formato Markdown"""
        rows = []

        # Headers
        headers = []
        header_row = table_element.find("tr")
        if header_row:
            for th in header_row.find_all(["th", "td"]):
                headers.append(clean_html_tags(th.get_text()).strip())

        if headers:
            rows.append("| " + " | ".join(headers) + " |")
            rows.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Data rows
        for tr in table_element.find_all("tr")[1:]:  # Skip header
            cells = []
            for td in tr.find_all(["td", "th"]):
                cell_text = clean_html_tags(td.get_text()).strip()
                # Pulisci caratteri problematici per Markdown
                cell_text = cell_text.replace("|", "\\|").replace("\n", " ")
                cells.append(cell_text)

            if cells:
                rows.append("| " + " | ".join(cells) + " |")

        return "\n".join(rows) if rows else ""

    def _extract_figure(
        self, figure_element: Tag, base_url: str
    ) -> Optional[Dict[str, str]]:
        """Estrae dati figure/immagini"""
        result = {"src": "", "alt": "", "caption": "", "type": "image"}

        # Trova img
        img = (
            figure_element.find("img")
            if figure_element.name != "img"
            else figure_element
        )

        if img:
            src = img.get("src", "")
            if src:
                result["src"] = (
                    urljoin(base_url, src) if not src.startswith("http") else src
                )

            result["alt"] = img.get("alt", "")

        # Trova caption
        caption_element = figure_element.find(["figcaption", "caption"])
        if caption_element:
            result["caption"] = clean_html_tags(caption_element.get_text()).strip()
        elif result["alt"]:
            result["caption"] = result["alt"]
        else:
            result["caption"] = "Immagine senza descrizione"

        return result if result["src"] or result["caption"] else None

    def _generate_anchor(self, title: str) -> str:
        """Genera anchor dal titolo"""
        # Converti in lowercase e sostituisci spazi/caratteri speciali
        anchor = re.sub(r"[^\w\s-]", "", title.lower())
        anchor = re.sub(r"[-\s]+", "-", anchor)
        return anchor.strip("-")

    def extract_parameters_from_section(self, section: HTMLSection) -> List[Dict]:
        """Estrae parametri strutturati da una sezione"""
        parameters = []

        if section.content_type != ContentType.PARAMETER:
            return parameters

        # Pattern per estrarre parametri dal testo
        param_patterns = [
            r"(?:Parametro|Campo|Opzione)\s*[:\-]?\s*([^\n]+)",
            r"([A-Z][a-z]+(?:\s+[a-z]+)*)\s*[:=]\s*([^\n]+)",
            r"•\s*([^:]+):\s*([^\n]+)",
        ]

        for pattern in param_patterns:
            matches = re.finditer(pattern, section.content, re.MULTILINE)
            for match in matches:
                if len(match.groups()) >= 2:
                    param_name = match.group(1).strip()
                    param_value = match.group(2).strip()

                    parameters.append(
                        {
                            "name": param_name,
                            "description": param_value,
                            "section_id": section.section_id,
                            "ui_path": section.ui_path or "",
                            "anchor": section.anchor,
                        }
                    )

        return parameters
