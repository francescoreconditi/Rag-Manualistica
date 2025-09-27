"""
Template tipizzati per la generazione di risposte.
Specializzati per Parametri, Procedure ed Errori di gestionali.
"""

from typing import Dict, List, Optional
from jinja2 import Environment, BaseLoader
from enum import Enum

from ..core.models import QueryType, SearchResult


class ResponseTemplate(Enum):
    """Template di risposta disponibili"""

    PARAMETER = "parameter"
    PROCEDURE = "procedure"
    ERROR = "error"
    GENERAL = "general"
    FALLBACK = "fallback"


class TemplateManager:
    """Gestore dei template per risposte tipizzate"""

    def __init__(self):
        self.jinja_env = Environment(loader=BaseLoader())
        self._load_templates()

    def _load_templates(self):
        """Carica tutti i template"""

        # Template per PARAMETRI
        self.parameter_template = """
**Parametro: {{ param_name }}**

{% if module %}**Modulo**: {{ module }}{% endif %}
{% if ui_path %}**Percorso**: {{ ui_path }}{% endif %}

**Descrizione**: {{ description }}

{% if values %}**Valori ammessi**: {{ values }}{% endif %}
{% if default_value %}**Valore predefinito**: {{ default_value }}{% endif %}
{% if constraints %}**Vincoli**: {{ constraints }}{% endif %}

{% if dependencies %}**Dipendenze**: {{ dependencies | join(', ') }}{% endif %}
{% if related_errors %}**Errori correlati**: {{ related_errors | join(', ') }}{% endif %}

{% if notes %}**Note operative**: {{ notes }}{% endif %}

{% if version %}**Versioni**: Disponibile dalla versione {{ version }}{% endif %}

**Fonti**:
{% for source in sources %}
- [{{ source.title }}]({{ source.url }}){% if source.anchor %}#{{ source.anchor }}{% endif %}
{% endfor %}
""".strip()

        # Template per PROCEDURE
        self.procedure_template = """
**{{ title }}**

{% if module %}**Modulo**: {{ module }}{% endif %}
{% if prerequisites %}**Prerequisiti**: {{ prerequisites }}{% endif %}

**Procedura**:
{% for step in steps %}
{{ loop.index }}. {{ step }}
{% endfor %}

{% if variants %}**Varianti**:
{{ variants }}{% endif %}

{% if output %}**Risultato atteso**: {{ output }}{% endif %}

{% if warnings %}⚠️ **Attenzione**: {{ warnings }}{% endif %}

**Fonti**:
{% for source in sources %}
- [{{ source.title }}]({{ source.url }}){% if source.anchor %}#{{ source.anchor }}{% endif %}
{% endfor %}
""".strip()

        # Template per ERRORI
        self.error_template = """
**Errore {{ error_code }}: {{ error_message }}**

{% if module %}**Modulo**: {{ module }}{% endif %}

**Causa probabile**: {{ cause }}

**Risoluzione**:
{% for step in resolution_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}

{% if prevention %}**Prevenzione**: {{ prevention }}{% endif %}

{% if related_params %}**Parametri correlati**: {{ related_params | join(', ') }}{% endif %}

**Fonti**:
{% for source in sources %}
- [{{ source.title }}]({{ source.url }}){% if source.anchor %}#{{ source.anchor }}{% endif %}
{% endfor %}
""".strip()

        # Template GENERALE
        self.general_template = """
**{{ title }}**

{{ content }}

{% if key_points and key_points|length > 0 %}

**Funzionalità principali**:
{% for point in key_points %}
- {{ point }}
{% endfor %}{% endif %}

{% if related_topics %}**Argomenti correlati**: {{ related_topics | join(', ') }}{% endif %}

**Fonti**:
{% for source in sources %}
- [{{ source.title }}]({{ source.url }}){% if source.anchor %}#{{ source.anchor }}{% endif %}
{% endfor %}
""".strip()

        # Template di FALLBACK
        self.fallback_template = """
**Informazione non trovata**

{{ fallback_message }}

{% if suggestions %}**Sezioni correlate che potrebbero essere utili**:
{% for suggestion in suggestions %}
- [{{ suggestion.title }}]({{ suggestion.url }})
{% endfor %}{% endif %}

{% if search_tips %}**Suggerimenti per la ricerca**:
{% for tip in search_tips %}
- {{ tip }}
{% endfor %}{% endif %}
""".strip()

    def get_template(self, template_type: ResponseTemplate) -> str:
        """Ottiene template per tipo"""
        template_map = {
            ResponseTemplate.PARAMETER: self.parameter_template,
            ResponseTemplate.PROCEDURE: self.procedure_template,
            ResponseTemplate.ERROR: self.error_template,
            ResponseTemplate.GENERAL: self.general_template,
            ResponseTemplate.FALLBACK: self.fallback_template,
        }
        return template_map.get(template_type, self.fallback_template)

    def render_template(self, template_type: ResponseTemplate, context: Dict) -> str:
        """
        Renderizza template con contesto

        Args:
            template_type: Tipo di template
            context: Dizionario con variabili per il template

        Returns:
            Template renderizzato
        """
        template_str = self.get_template(template_type)
        template = self.jinja_env.from_string(template_str)
        return template.render(**context)


class ContextBuilder:
    """Costruttore di contesto per i template"""

    def __init__(self):
        self.template_manager = TemplateManager()

    def build_parameter_context(
        self, sources: List[SearchResult], param_name: Optional[str] = None
    ) -> Dict:
        """Costruisce contesto per template parametro"""
        if not sources:
            return {}

        primary_source = sources[0]
        metadata = primary_source.chunk.metadata
        content = primary_source.chunk.content

        # Estrai informazioni dal contenuto
        param_info = self._extract_parameter_info(content, param_name)

        context = {
            "param_name": param_name or metadata.param_name or metadata.title,
            "module": metadata.module,
            "ui_path": metadata.ui_path,
            "description": param_info.get("description", ""),
            "values": param_info.get("values"),
            "default_value": param_info.get("default"),
            "constraints": param_info.get("constraints"),
            "dependencies": param_info.get("dependencies", []),
            "related_errors": param_info.get("related_errors", []),
            "notes": param_info.get("notes"),
            "version": metadata.version,
            "sources": self._format_sources(sources),
        }

        return context

    def build_procedure_context(self, sources: List[SearchResult], query: str) -> Dict:
        """Costruisce contesto per template procedura"""
        if not sources:
            return {}

        primary_source = sources[0]
        metadata = primary_source.chunk.metadata
        content = primary_source.chunk.content

        # Estrai steps dalla procedura
        procedure_info = self._extract_procedure_info(content)

        context = {
            "title": metadata.title,
            "module": metadata.module,
            "prerequisites": procedure_info.get("prerequisites"),
            "steps": procedure_info.get("steps", []),
            "variants": procedure_info.get("variants"),
            "output": procedure_info.get("output"),
            "warnings": procedure_info.get("warnings"),
            "sources": self._format_sources(sources),
        }

        return context

    def build_error_context(
        self, sources: List[SearchResult], error_code: Optional[str] = None
    ) -> Dict:
        """Costruisce contesto per template errore"""
        if not sources:
            return {}

        primary_source = sources[0]
        metadata = primary_source.chunk.metadata
        content = primary_source.chunk.content

        # Estrai informazioni errore
        error_info = self._extract_error_info(content, error_code)

        context = {
            "error_code": error_code or metadata.error_code or "N/A",
            "error_message": error_info.get("message", ""),
            "module": metadata.module,
            "cause": error_info.get("cause", ""),
            "resolution_steps": error_info.get("resolution_steps", []),
            "prevention": error_info.get("prevention"),
            "related_params": error_info.get("related_params", []),
            "sources": self._format_sources(sources),
        }

        return context

    def build_general_context(self, sources: List[SearchResult], query: str) -> Dict:
        """Costruisce contesto per template generale"""
        if not sources:
            return {}

        primary_source = sources[0]
        metadata = primary_source.chunk.metadata

        # Combina contenuti
        combined_content = self._combine_content(sources)
        key_points = self._extract_key_points(combined_content)

        context = {
            "title": metadata.title,
            "content": combined_content,
            "key_points": [],  # Temporaneamente disabilitato per evitare ripetizioni
            "related_topics": self._extract_related_topics(sources),
            "sources": self._format_sources(sources),
        }

        return context

    def build_fallback_context(
        self, query: str, suggestions: List[SearchResult] = None
    ) -> Dict:
        """Costruisce contesto per template fallback"""
        context = {
            "fallback_message": "L'informazione richiesta non è disponibile nella documentazione indicizzata.",
            "suggestions": self._format_sources(suggestions or []),
            "search_tips": [
                "Prova a utilizzare sinonimi o termini alternativi",
                "Verifica la versione del modulo a cui ti riferisci",
                'Includi il nome del modulo nella ricerca (es. "Contabilità", "Fatturazione")',
                'Per errori, indica il codice completo (es. "IVA-102")',
            ],
        }

        return context

    def _extract_parameter_info(
        self, content: str, param_name: Optional[str] = None
    ) -> Dict:
        """Estrae informazioni parametro dal contenuto"""
        import re

        info = {}

        # Descrizione - prendi primo paragrafo
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if len(line) > 20 and not line.startswith("*") and not line.startswith("#"):
                info["description"] = line
                break

        # Valori ammessi
        values_match = re.search(
            r"(?:valori|opzioni)\s*[:=]\s*([^\n]+)", content, re.IGNORECASE
        )
        if values_match:
            info["values"] = values_match.group(1).strip()

        # Default
        default_match = re.search(
            r"(?:default|predefinito)\s*[:=]\s*([^\n]+)", content, re.IGNORECASE
        )
        if default_match:
            info["default"] = default_match.group(1).strip()

        # Vincoli
        constraints_match = re.search(
            r"(?:vincol|limitazion)\w*\s*[:=]\s*([^\n]+)", content, re.IGNORECASE
        )
        if constraints_match:
            info["constraints"] = constraints_match.group(1).strip()

        return info

    def _extract_procedure_info(self, content: str) -> Dict:
        """Estrae informazioni procedura dal contenuto"""
        import re

        info = {}

        # Estrai steps numerati
        step_patterns = [
            r"^\d+\.\s+(.+)$",  # 1. Step
            r"^\d+\)\s+(.+)$",  # 1) Step
            r"^-\s+(.+)$",  # - Step
            r"^•\s+(.+)$",  # • Step
        ]

        steps = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            for pattern in step_patterns:
                match = re.match(pattern, line)
                if match:
                    steps.append(match.group(1))
                    break

        if steps:
            info["steps"] = steps

        # Prerequisites
        prereq_match = re.search(
            r"(?:prerequisit|prima di)\w*\s*[:=]\s*([^\n]+)", content, re.IGNORECASE
        )
        if prereq_match:
            info["prerequisites"] = prereq_match.group(1).strip()

        # Warnings
        warning_match = re.search(
            r"(?:attenzione|avviso|warning)\s*[:!]\s*([^\n]+)", content, re.IGNORECASE
        )
        if warning_match:
            info["warnings"] = warning_match.group(1).strip()

        return info

    def _extract_error_info(
        self, content: str, error_code: Optional[str] = None
    ) -> Dict:
        """Estrae informazioni errore dal contenuto"""
        import re

        info = {}

        # Messaggio errore
        if error_code:
            message_match = re.search(f"{error_code}[:\-]?\s*([^\n]+)", content)
            if message_match:
                info["message"] = message_match.group(1).strip()

        # Causa
        cause_match = re.search(
            r"(?:causa|motivo|dovuto)\w*\s*[:=]\s*([^\n]+)", content, re.IGNORECASE
        )
        if cause_match:
            info["cause"] = cause_match.group(1).strip()

        # Risoluzione steps
        resolution_patterns = [
            r"(?:risoluzione|soluzione)\s*[:=]\s*(.+?)(?=\n\n|\Z)",
            r"(?:per risolvere|correggere)\s*[:=]\s*(.+?)(?=\n\n|\Z)",
        ]

        for pattern in resolution_patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                resolution_text = match.group(1).strip()
                # Dividi in steps se numerati
                steps = []
                for line in resolution_text.split("\n"):
                    line = line.strip()
                    if re.match(r"^\d+[\.\)]\s+", line):
                        steps.append(re.sub(r"^\d+[\.\)]\s+", "", line))
                    elif line and not steps:
                        steps.append(line)

                if steps:
                    info["resolution_steps"] = steps
                break

        return info

    def _combine_content(self, sources: List[SearchResult]) -> str:
        """Combina contenuto da multiple sources"""
        combined = []
        seen_content = set()

        for source in sources[:5]:  # Limita a top 5
            content = source.chunk.content.strip()

            # Deduplica contenuti identici
            content_hash = hash(content)
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)

            # Usa contenuto completo se ragionevole, altrimenti tronca intelligentemente
            if len(content) <= 800:
                combined.append(content)
            else:
                # Trova un punto di interruzione naturale
                truncate_at = 600
                last_sentence = content.rfind(".", 0, truncate_at)
                if last_sentence > 400:
                    truncated = content[: last_sentence + 1]
                else:
                    truncated = content[:truncate_at] + "..."
                combined.append(truncated)

        return "\n\n".join(combined)

    def _extract_key_points(self, content: str) -> List[str]:
        """Estrae punti chiave dal contenuto"""
        import re

        points = []

        # Cerca bullet points esistenti
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if re.match(r"^[-•*]\s+(.+)", line):
                point = re.sub(r"^[-•*]\s+", "", line)
                points.append(point)

        # Se non ci sono bullet, cerca pattern di funzionalità
        if not points:
            # Cerca pattern come "chiudendo...", "calcolando...", "generando..."
            # Spezza il testo dove ci sono questi verbi
            action_verbs = r"\b(chiudendo|calcolando|generando|producendo|fornendo)\s+"
            parts = re.split(action_verbs, content, flags=re.IGNORECASE)

            current_action = None
            for i, part in enumerate(parts):
                part = part.strip()
                if part.lower() in [
                    "chiudendo",
                    "calcolando",
                    "generando",
                    "producendo",
                    "fornendo",
                ]:
                    current_action = part
                elif current_action and len(part) > 10:
                    # Prendi solo la prima parte fino al prossimo verbo o punto
                    description = part.split()[0:8]  # Prime 8 parole
                    if description:
                        points.append(
                            f"{current_action.capitalize()} {' '.join(description)}"
                        )
                    current_action = None
                    if len(points) >= 4:  # Limite massimo
                        break

        # Se ancora nessun punto, cerca frasi che iniziano con parole chiave
        if not points:
            key_phrases = r"\b(permette|consente|agevola|gestisce|include)\s+([^\.]+)"
            phrases = re.findall(key_phrases, content, re.IGNORECASE)

            for verb, description in phrases:
                if len(description.strip()) > 15:
                    points.append(f"{verb.capitalize()} {description.strip()}")

        # Come ultima risorsa, usa titoli delle sottosezioni
        if not points:
            section_titles = re.findall(r"^([A-Z][^\.]+)$", content, re.MULTILINE)
            for title in section_titles:
                if (
                    len(title.strip()) > 5 and title not in content[:100]
                ):  # Non duplicare il titolo principale
                    points.append(title.strip())

        return points[:4]  # Max 4 punti per evitare sovraffollamento

    def _extract_related_topics(self, sources: List[SearchResult]) -> List[str]:
        """Estrae argomenti correlati dalle sources"""
        topics = set()

        for source in sources:
            breadcrumbs = source.chunk.metadata.breadcrumbs
            if breadcrumbs:
                topics.update(breadcrumbs)

        return list(topics)[:5]  # Max 5 topics

    def _format_sources(self, sources: List[SearchResult]) -> List[Dict]:
        """Formatta sources per i template"""
        formatted = []

        for source in sources:
            metadata = source.chunk.metadata
            formatted.append(
                {
                    "title": metadata.title,
                    "url": metadata.source_url,
                    "anchor": metadata.anchor,
                }
            )

        return formatted
