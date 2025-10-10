"""
Parser PDF specializzato per manuali tecnici.
Estrae testo, tabelle e metadati con preservazione della struttura.
"""

import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import fitz  # PyMuPDF
import camelot
from tabula import read_pdf

from ..core.models import ContentType, SourceFormat
from ..core.utils import (
    clean_html_tags,
    normalize_text,
    extract_error_codes,
    estimate_tokens,
)


class PDFSection:
    """Rappresenta una sezione del documento PDF"""

    def __init__(
        self,
        title: str,
        content: str,
        level: int,
        page_start: int,
        page_end: int,
        bbox: Optional[Tuple[float, float, float, float]] = None,
    ):
        self.title = title
        self.content = content
        self.level = level
        self.page_start = page_start
        self.page_end = page_end
        self.bbox = bbox  # Bounding box (x0, y0, x1, y1)
        # IMPORTANTE: error_codes deve essere inizializzato PRIMA di _classify_content()
        # perché _classify_content() usa self.error_codes
        self.error_codes = extract_error_codes(content)
        self.content_type = self._classify_content()
        self.tables: List[str] = []
        self.figures: List[Dict[str, str]] = []

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

        if (
            any(pattern in content_lower for pattern in error_patterns)
            or self.error_codes
        ):
            return ContentType.ERROR

        if any(pattern in title_lower for pattern in param_patterns):
            return ContentType.PARAMETER

        if any(pattern in content_lower for pattern in procedure_patterns):
            return ContentType.PROCEDURE

        if any(pattern in title_lower for pattern in table_patterns):
            return ContentType.TABLE

        if "faq" in title_lower or "domande" in title_lower:
            return ContentType.FAQ

        return ContentType.CONCEPT


class PDFParser:
    """Parser PDF per manuali di gestionali"""

    def __init__(self):
        # Parametri per rilevamento headings
        self.min_heading_size = 12  # Dimensione minima font per heading
        self.heading_size_threshold = 2  # Differenza minima con testo normale

        # Font comuni per headings
        self.heading_fonts = [
            "arial",
            "helvetica",
            "times",
            "calibri",
            "verdana",
        ]

        # Pattern per numerazione sezioni
        self.section_patterns = [
            r"^\d+\.\s+",  # 1. Titolo
            r"^\d+\.\d+\s+",  # 1.1 Sottotitolo
            r"^[A-Z]\.\s+",  # A. Appendice
            r"^[IVX]+\.\s+",  # I. Romano
        ]

    def parse_from_path(self, pdf_path: str) -> Tuple[List[PDFSection], Dict]:
        """
        Parse PDF da file

        Args:
            pdf_path: Percorso al file PDF

        Returns:
            Tuple di (sezioni, metadati)
        """
        doc = fitz.open(pdf_path)

        try:
            # Estrai metadati
            metadata = self._extract_metadata(doc, pdf_path)

            # Analizza struttura del documento
            font_stats = self._analyze_fonts(doc)

            # Estrai sezioni
            sections = self._extract_sections(doc, font_stats)

            # Estrai tabelle
            self._extract_tables(pdf_path, sections)

            return sections, metadata

        finally:
            doc.close()

    def _extract_metadata(self, doc: fitz.Document, pdf_path: str) -> Dict:
        """Estrae metadati dal documento PDF"""
        metadata = {
            "source_url": f"file://{pdf_path}",
            "source_format": SourceFormat.PDF,
            "title": "",
            "description": "",
            "module": "",
            "version": "",
            "page_count": doc.page_count,
            "creation_date": None,
            "modification_date": None,
        }

        # Metadati PDF
        pdf_metadata = doc.metadata
        if pdf_metadata:
            metadata["title"] = pdf_metadata.get("title", "")
            metadata["description"] = pdf_metadata.get("subject", "")
            metadata["creation_date"] = pdf_metadata.get("creationDate")
            metadata["modification_date"] = pdf_metadata.get("modDate")

        # Se non c'è titolo, usa il nome del file
        if not metadata["title"]:
            metadata["title"] = Path(pdf_path).stem

        # Cerca modulo e versione nel titolo
        if metadata["title"]:
            module_match = re.search(
                r"(Contabilità|Fatturazione|Magazzino|HR|Desktop\w+)",
                metadata["title"],
                re.IGNORECASE,
            )
            if module_match:
                metadata["module"] = module_match.group(1)

            version_match = re.search(r"v?(\d+\.\d+(?:\.\d+)?)", metadata["title"])
            if version_match:
                metadata["version"] = version_match.group(1)

        return metadata

    def _analyze_fonts(self, doc: fitz.Document) -> Dict:
        """Analizza i font del documento per identificare i livelli di heading"""
        font_stats = {}

        # Analizza prime 5 pagine per campionare i font
        sample_pages = min(5, doc.page_count)

        for page_num in range(sample_pages):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue

                for line in block["lines"]:
                    for span in line["spans"]:
                        font_name = span["font"].lower()
                        font_size = span["size"]
                        font_flags = span["flags"]  # Bold, italic, etc.

                        key = (font_name, font_size, font_flags)
                        if key not in font_stats:
                            font_stats[key] = {"count": 0, "avg_length": 0}

                        font_stats[key]["count"] += 1
                        text_length = len(span["text"].strip())
                        font_stats[key]["avg_length"] = (
                            font_stats[key]["avg_length"] + text_length
                        ) / 2

        # Identifica font per headings (grandi, poco frequenti, testo breve)
        heading_fonts = {}
        if font_stats:
            max_size = max(key[1] for key in font_stats.keys())
            avg_size = sum(key[1] for key in font_stats.keys()) / len(font_stats)

            for (font_name, font_size, font_flags), stats in font_stats.items():
                # Criteri per heading
                is_large = font_size >= avg_size + self.heading_size_threshold
                is_bold = font_flags & 2**4  # Bold flag
                is_short = stats["avg_length"] < 50
                is_rare = stats["count"] < len(font_stats) * 0.1

                if (is_large or is_bold) and (is_short or is_rare):
                    level = int((max_size - font_size) / 2) + 1
                    heading_fonts[(font_name, font_size, font_flags)] = min(level, 6)

        return heading_fonts

    def _extract_sections(
        self, doc: fitz.Document, heading_fonts: Dict
    ) -> List[PDFSection]:
        """Estrae sezioni dal documento"""
        sections = []
        current_section = None
        section_counter = 0

        for page_num in range(doc.page_count):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue

                # Estrai testo del blocco
                block_text = ""
                is_heading = False
                heading_level = 0
                bbox = block.get("bbox")

                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        span_text = span["text"]
                        line_text += span_text

                        # Verifica se è un heading
                        font_key = (
                            span["font"].lower(),
                            span["size"],
                            span["flags"],
                        )
                        if font_key in heading_fonts:
                            is_heading = True
                            heading_level = heading_fonts[font_key]

                    block_text += line_text + "\n"

                block_text = normalize_text(block_text)

                # Se è un heading, inizia nuova sezione
                if is_heading and len(block_text.strip()) > 0:
                    # Finalizza sezione precedente
                    if current_section:
                        sections.append(current_section)

                    # Crea nuova sezione
                    section_counter += 1
                    title = block_text.strip()

                    current_section = PDFSection(
                        title=title,
                        content="",
                        level=heading_level,
                        page_start=page_num + 1,
                        page_end=page_num + 1,
                        bbox=bbox,
                    )

                # Altrimenti aggiungi alla sezione corrente
                elif current_section and len(block_text.strip()) > 0:
                    if current_section.content:
                        current_section.content += "\n\n"
                    current_section.content += block_text
                    current_section.page_end = page_num + 1

        # Aggiungi ultima sezione
        if current_section:
            sections.append(current_section)

        # Filtra sezioni troppo corte e pulisci contenuto
        filtered_sections = []
        for section in sections:
            if len(section.content) > 50:  # Minimo 50 caratteri
                # Pulisci contenuto
                section.content = self._clean_pdf_text(section.content)
                filtered_sections.append(section)

        return filtered_sections

    def _clean_pdf_text(self, text: str) -> str:
        """Pulisce il testo estratto dal PDF"""
        # Rimuovi caratteri di controllo
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]", "", text)

        # Rimuovi righe con solo numeri di pagina
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            # Salta righe vuote o solo numeri (probabilmente num. pagina)
            if not line or line.isdigit():
                continue
            # Salta header/footer ripetitivi
            if len(line) < 5 and not any(char.isalpha() for char in line):
                continue

            cleaned_lines.append(line)

        # Ricomponi e normalizza
        text = "\n".join(cleaned_lines)
        return normalize_text(text)

    def _extract_tables(self, pdf_path: str, sections: List[PDFSection]) -> None:
        """Estrae tabelle dal PDF e le associa alle sezioni"""
        try:
            # Prova Camelot per tabelle con bordi
            tables_camelot = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")

            for table in tables_camelot:
                table_text = self._table_to_markdown(table.df)
                page_num = table.parsing_report["page"]

                # Trova sezione corrispondente
                for section in sections:
                    if section.page_start <= page_num <= section.page_end:
                        section.tables.append(table_text)
                        section.content_type = ContentType.TABLE
                        break

        except Exception:
            # Fallback con tabula per tabelle senza bordi
            try:
                tables_tabula = read_pdf(pdf_path, pages="all", multiple_tables=True)
                for i, df in enumerate(tables_tabula):
                    if not df.empty:
                        table_text = self._table_to_markdown(df)
                        # Associa alla prima sezione (semplificato)
                        if sections:
                            sections[0].tables.append(table_text)
            except Exception:
                pass  # Ignora errori nell'estrazione tabelle

    def _table_to_markdown(self, df) -> str:
        """Converte DataFrame in formato Markdown"""
        try:
            # Pulisci i dati
            df = df.fillna("")
            df = df.astype(str)

            # Converti in Markdown
            markdown_lines = []

            # Header
            headers = [str(col).strip() for col in df.columns]
            if headers and any(headers):
                markdown_lines.append("| " + " | ".join(headers) + " |")
                markdown_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

            # Righe
            for _, row in df.iterrows():
                cells = [str(cell).strip().replace("|", "\\|") for cell in row]
                if any(cells):  # Solo se la riga ha contenuto
                    markdown_lines.append("| " + " | ".join(cells) + " |")

            return "\n".join(markdown_lines)

        except Exception:
            return str(df)  # Fallback

    def extract_images_with_ocr(
        self, doc: fitz.Document, page_num: int
    ) -> List[Dict[str, str]]:
        """
        Estrae immagini dalla pagina e applica OCR se necessario.
        Questo metodo può essere esteso per OCR di screenshot UI.
        """
        images = []
        page = doc[page_num]

        image_list = page.get_images()
        for img_index, img in enumerate(image_list):
            # Estrai immagine
            xref = img[0]
            pix = fitz.Pixmap(doc, xref)

            if pix.n - pix.alpha < 4:  # Solo immagini RGB/Gray
                img_data = {
                    "page": page_num + 1,
                    "index": img_index,
                    "width": pix.width,
                    "height": pix.height,
                    "caption": f"Immagine {img_index + 1} - Pagina {page_num + 1}",
                    "ocr_text": "",  # Placeholder per OCR futuro
                }
                images.append(img_data)

            pix = None  # Libera memoria

        return images
