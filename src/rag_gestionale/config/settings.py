"""
Configurazione centralizzata del sistema RAG.
Utilizza pydantic-settings per gestione di environment variables e config files.
"""

from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChunkingSettings(BaseModel):
    """Configurazione per il chunking"""

    # Parent chunks (sezioni complete)
    parent_max_tokens: int = Field(
        default=800, description="Token massimi per chunk parent"
    )
    parent_overlap_tokens: int = Field(
        default=100, description="Overlap tra chunk parent"
    )

    # Child chunks procedurali
    child_proc_max_tokens: int = Field(
        default=350, description="Token massimi per chunk procedurali"
    )
    child_proc_overlap_tokens: int = Field(
        default=50, description="Overlap tra chunk procedurali"
    )

    # Child chunks parametri
    child_param_max_tokens: int = Field(
        default=200, description="Token massimi per chunk parametri"
    )
    child_param_overlap_tokens: int = Field(
        default=0, description="No overlap per parametri"
    )

    # Tabelle
    table_max_rows: int = Field(
        default=25, description="Righe massime per chunk tabella"
    )


class EmbeddingSettings(BaseModel):
    """Configurazione per gli embeddings"""

    model_name: str = Field(default="BAAI/bge-m3", description="Modello per embeddings")
    normalize_embeddings: bool = Field(default=True, description="Normalizzazione L2")
    batch_size: int = Field(
        default=8, description="Batch size per embedding CPU (ridotto per stabilità)"
    )
    batch_size_gpu: int = Field(default=128, description="Batch size per embedding GPU")
    max_length: int = Field(default=512, description="Lunghezza massima input")


class VectorStoreSettings(BaseModel):
    """Configurazione per il vector store (Qdrant)"""

    host: str = Field(default="localhost", description="Host Qdrant")
    port: int = Field(default=6333, description="Porta Qdrant")
    collection_name: str = Field(
        default="gestionale_docs", description="Nome collection"
    )

    # Parametri HNSW
    hnsw_m: int = Field(default=64, description="Parametro M per HNSW")
    hnsw_ef_construct: int = Field(default=256, description="efConstruction per HNSW")
    hnsw_ef_search: int = Field(default=64, description="efSearch per HNSW")


class LexicalSearchSettings(BaseModel):
    """Configurazione per la ricerca lessicale (OpenSearch)"""

    host: str = Field(default="localhost", description="Host OpenSearch")
    port: int = Field(default=9200, description="Porta OpenSearch")
    index_name: str = Field(default="gestionale_lexical", description="Nome indice")

    # Parametri BM25
    bm25_k1: float = Field(default=0.9, description="Parametro k1 per BM25")
    bm25_b: float = Field(default=0.55, description="Parametro b per BM25")


class RetrievalSettings(BaseModel):
    """Configurazione per il retrieval"""

    # Ibrido
    k_dense: int = Field(default=40, description="Top-k per ricerca densa")
    k_lexical: int = Field(default=20, description="Top-k per ricerca lessicale")
    k_rerank: int = Field(default=30, description="Candidati per reranking")
    k_final: int = Field(default=10, description="Risultati finali")

    # Booster per campi
    title_boost: float = Field(default=1.4, description="Boost per titoli")
    breadcrumbs_boost: float = Field(default=1.2, description="Boost per breadcrumbs")
    param_name_boost: float = Field(default=2.0, description="Boost per nomi parametri")
    error_code_boost: float = Field(default=2.5, description="Boost per codici errore")

    # Reranker
    reranker_model: str = Field(
        default="BAAI/bge-reranker-large", description="Modello reranker"
    )
    diversification_threshold: int = Field(
        default=2, description="Max risultati per sezione"
    )


class LLMSettings(BaseModel):
    """Configurazione per LLM (OpenAI)"""

    enabled: bool = Field(default=False, description="Abilita integrazione LLM")
    api_key: str = Field(default="", description="API key OpenAI")
    model_name: str = Field(
        default="gpt-4o-mini", description="Modello OpenAI da usare"
    )
    max_tokens: int = Field(default=1500, description="Token massimi risposta LLM")
    temperature: float = Field(default=0.2, description="Temperatura LLM")
    timeout: int = Field(default=30, description="Timeout richieste LLM (secondi)")

    # Controllo costi
    max_requests_per_minute: int = Field(default=20, description="Limite richieste/min")
    use_llm_for_complex_queries: bool = Field(
        default=True, description="Usa LLM solo per query complesse"
    )


class GenerationSettings(BaseModel):
    """Configurazione per la generazione"""

    max_context_chunks: int = Field(default=6, description="Chunk massimi nel contesto")
    max_context_tokens: int = Field(
        default=8000, description="Token massimi nel contesto"
    )
    temperature: float = Field(default=0.1, description="Temperatura per generazione")

    # Modalità generazione
    generation_mode: str = Field(
        default="hybrid", description="Modalità: template, llm, hybrid"
    )

    # Template
    citation_required: bool = Field(default=False, description="Citazioni obbligatorie")
    fallback_message: str = Field(
        default="L'informazione richiesta non è disponibile nella documentazione indicizzata.",
        description="Messaggio di fallback",
    )


class ImageStorageSettings(BaseModel):
    """Configurazione per storage immagini"""

    storage_base_path: str = Field(
        default="./storage/images", description="Percorso base storage immagini"
    )
    min_width: int = Field(
        default=100,
        description="Larghezza minima immagini (px) - aumentato per escludere icone",
    )
    min_height: int = Field(
        default=100,
        description="Altezza minima immagini (px) - aumentato per escludere icone",
    )
    max_file_size_mb: int = Field(
        default=10, description="Dimensione massima file (MB)"
    )
    enabled: bool = Field(
        default=False,
        description="Abilita estrazione immagini (DISABILITATO temporaneamente per concentrarsi sul testo)",
    )

    # OCR
    ocr_enabled: bool = Field(default=True, description="Abilita OCR su immagini")
    ocr_languages: str = Field(
        default="ita+eng", description="Lingue OCR (formato Tesseract)"
    )
    ocr_min_confidence: int = Field(
        default=30, description="Confidenza minima OCR (0-100)"
    )
    ocr_preprocessing: bool = Field(
        default=True, description="Abilita pre-processing immagini per OCR"
    )
    ocr_timeout_seconds: int = Field(default=30, description="Timeout OCR per immagine")


class IngestSettings(BaseModel):
    """Configurazione per l'ingestione"""

    # Crawling
    max_concurrent_requests: int = Field(
        default=10, description="Richieste concorrenti massime"
    )
    request_delay_ms: int = Field(default=1000, description="Delay tra richieste")
    user_agent: str = Field(
        default="RAG-Gestionale/1.0", description="User agent per crawling"
    )

    # Parsing
    min_content_length: int = Field(
        default=100, description="Lunghezza minima contenuto"
    )
    similarity_threshold: float = Field(
        default=0.92, description="Soglia per deduplicazione"
    )
    max_html_size_chars: int = Field(
        default=500000, description="Dimensione massima HTML in caratteri (500K)"
    )
    parsing_timeout_seconds: int = Field(
        default=120, description="Timeout parsing HTML/PDF in secondi"
    )
    embedding_timeout_seconds: int = Field(
        default=300, description="Timeout generazione embeddings in secondi"
    )

    # Batch processing per grandi documenti
    sections_batch_size: int = Field(
        default=15, description="Numero di sezioni da processare per batch"
    )
    enable_streaming_ingest: bool = Field(
        default=True, description="Abilita ingestione streaming per grandi file"
    )

    # Formati supportati
    supported_extensions: List[str] = Field(
        default=[".html", ".htm", ".pdf", ".md"],
        description="Estensioni file supportate",
    )


class Settings(BaseSettings):
    """Configurazione principale del sistema"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RAG_",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    # Device configuration
    device_mode: str = Field(
        default="auto",
        description="Modalità device: 'auto' (usa GPU se disponibile), 'cuda' (forza GPU), 'cpu' (forza CPU)",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Livello di logging")
    log_format: str = Field(
        default="<time>{time:YYYY-MM-DD HH:mm:ss}</time> | <level>{level: <8}</level> | <message>{message}</message>",
        description="Formato log",
    )

    # API
    api_host: str = Field(default="0.0.0.0", description="Host API")
    api_port: int = Field(default=8000, description="Porta API")
    api_workers: int = Field(default=1, description="Worker API")

    # Whitelisting domini - usa i default nel codice
    allowed_domains: List[str] = Field(
        default=[
            "cassiopea.centrosistemi.it",
            "docs.centrosistemi.it",
            "docs.example.com",
            "10.1.1.1",  # Wiki interna
            "192.168.0.12",  # Server PDF locale
            "localhost",  # Sviluppo locale
            "127.0.0.1",  # Sviluppo locale
        ],
        description="Domini autorizzati per crawling",
    )

    # Sottoconfigurazioni
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    lexical_search: LexicalSearchSettings = Field(default_factory=LexicalSearchSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    ingest: IngestSettings = Field(default_factory=IngestSettings)
    image_storage: ImageStorageSettings = Field(default_factory=ImageStorageSettings)


# Istanza globale delle impostazioni
settings = Settings()


def get_settings() -> Settings:
    """Factory per ottenere le impostazioni"""
    return settings


def get_device() -> str:
    """
    Determina il device da utilizzare basandosi sulla configurazione.

    Returns:
        str: "cuda" se GPU disponibile e abilitata, "cpu" altrimenti
    """
    device_mode = settings.device_mode.lower()

    if device_mode == "cpu":
        return "cpu"
    elif device_mode == "cuda":
        # Forza CUDA senza verificare disponibilità (lancerà errore se non disponibile)
        return "cuda"
    else:  # "auto" o qualsiasi altro valore
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"
