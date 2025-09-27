"""
Modelli core del sistema RAG.
Definisce le strutture dati principali per documenti, chunk e metadati.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """Tipi di contenuto supportati"""
    PROCEDURE = "procedure"
    PARAMETER = "parameter"
    CONCEPT = "concept"
    FAQ = "faq"
    ERROR = "error"
    TABLE = "table"
    FIGURE = "figure"


class QueryType(str, Enum):
    """Tipi di query classificate"""
    PARAMETER = "parameter"
    PROCEDURE = "procedure"
    ERROR = "error"
    GENERAL = "general"


class SourceFormat(str, Enum):
    """Formati di sorgente supportati"""
    HTML = "html"
    PDF = "pdf"
    MARKDOWN = "markdown"


class ChunkMetadata(BaseModel):
    """Metadati ricchi per ogni chunk"""

    # Identificazione
    id: str = Field(..., description="ID univoco del chunk")
    title: str = Field(..., description="Titolo della sezione")
    breadcrumbs: List[str] = Field(default_factory=list, description="Percorso gerarchico")

    # Struttura
    section_level: int = Field(..., description="Livello della sezione (1-6)")
    section_path: str = Field(..., description="Percorso della sezione")
    content_type: ContentType = Field(..., description="Tipo di contenuto")

    # Versioning semplificato (una versione per manuale)
    version: str = Field(..., description="Versione del manuale")
    module: str = Field(..., description="Modulo del gestionale")

    # Parametri specifici (se applicabile)
    param_name: Optional[str] = Field(None, description="Nome del parametro")
    ui_path: Optional[str] = Field(None, description="Percorso nell'interfaccia")
    error_code: Optional[str] = Field(None, description="Codice errore")

    # Sorgente
    source_url: str = Field(..., description="URL della sorgente")
    source_format: SourceFormat = Field(..., description="Formato della sorgente")
    page_range: Optional[List[int]] = Field(None, description="Range di pagine (per PDF)")
    anchor: Optional[str] = Field(None, description="Ancora HTML")

    # Qualità e tracking
    lang: str = Field(default="it", description="Lingua del contenuto")
    hash: str = Field(..., description="Hash del contenuto per deduplicazione")
    updated_at: datetime = Field(default_factory=datetime.now, description="Data aggiornamento")

    # Relazioni gerarchiche
    parent_chunk_id: Optional[str] = Field(None, description="ID del chunk parent")
    child_chunk_ids: List[str] = Field(default_factory=list, description="ID dei chunk child")


class DocumentChunk(BaseModel):
    """Chunk di documento con contenuto e metadati"""

    content: str = Field(..., description="Contenuto testuale del chunk")
    metadata: ChunkMetadata = Field(..., description="Metadati del chunk")

    # Embeddings (popolati durante l'indicizzazione)
    dense_embedding: Optional[List[float]] = Field(None, description="Embedding denso")
    sparse_embedding: Optional[Dict[str, float]] = Field(None, description="Embedding sparso")

    # Cache per performance
    summary: Optional[str] = Field(None, description="Riassunto del chunk (2-3 frasi)")
    keywords: List[str] = Field(default_factory=list, description="Keywords estratte")


class ParameterRecord(BaseModel):
    """Record strutturato per parametri del gestionale"""

    name: str = Field(..., description="Nome del parametro")
    module: str = Field(..., description="Modulo di appartenenza")
    section_path: str = Field(..., description="Percorso della sezione")
    ui_path: str = Field(..., description="Percorso nell'interfaccia utente")

    # Dettagli del parametro
    type: str = Field(..., description="Tipo del parametro (enum, string, number, etc.)")
    allowed_values: Optional[List[str]] = Field(None, description="Valori ammessi")
    default_value: Optional[str] = Field(None, description="Valore predefinito")
    constraints: Optional[str] = Field(None, description="Vincoli e limitazioni")

    # Relazioni
    dependencies: List[str] = Field(default_factory=list, description="Dipendenze da altri parametri")
    related_errors: List[str] = Field(default_factory=list, description="Errori correlati")

    # Metadati
    version: str = Field(..., description="Versione del manuale")
    doc_anchor: str = Field(..., description="Ancora alla documentazione")
    updated_at: datetime = Field(default_factory=datetime.now)


class SearchRequest(BaseModel):
    """Richiesta di ricerca"""

    query: str = Field(..., description="Query dell'utente")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filtri opzionali")
    top_k: int = Field(default=10, description="Numero di risultati da restituire")
    include_metadata: bool = Field(default=True, description="Includere metadati nei risultati")


class SearchResult(BaseModel):
    """Risultato di ricerca"""

    chunk: DocumentChunk = Field(..., description="Chunk trovato")
    score: float = Field(..., description="Score di rilevanza")
    explanation: Optional[str] = Field(None, description="Spiegazione del matching")


class RAGResponse(BaseModel):
    """Risposta finale del sistema RAG"""

    query: str = Field(..., description="Query originale")
    query_type: QueryType = Field(..., description="Tipo di query classificato")
    answer: str = Field(..., description="Risposta generata")
    sources: List[SearchResult] = Field(..., description="Fonti utilizzate")
    confidence: float = Field(..., description="Confidenza della risposta (0-1)")
    processing_time_ms: int = Field(..., description="Tempo di elaborazione in ms")