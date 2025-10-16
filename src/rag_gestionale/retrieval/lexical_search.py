"""
Ricerca lessicale con OpenSearch/Elasticsearch.
Ottimizzato per termini tecnici italiani e codici errore.
"""

import asyncio
from typing import Dict, List, Optional, Any

from opensearchpy import AsyncOpenSearch
from loguru import logger

from ..core.models import DocumentChunk, SearchResult
from ..config.settings import get_settings


class LexicalSearch:
    """Ricerca lessicale con OpenSearch"""

    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[AsyncOpenSearch] = None
        self.index_name = self.settings.lexical_search.index_name

        # Analyzer italiano personalizzato
        self.italian_analyzer = {
            "tokenizer": "standard",
            "filter": [
                "lowercase",
                "asciifolding",  # Rimuove accenti
                "italian_stop",  # Stop words italiane
                "italian_stemmer",  # Stemming leggero
                "custom_synonym",  # Sinonimi personalizzati
            ],
        }

        # Sinonimi per terminologia gestionale
        self.custom_synonyms = [
            "impostazione,impostaz,settaggio,configurazione,config",
            "parametro,parametr,opzione,campo",
            "procedura,processo,guida,istruzione",
            "errore,error,codice,avviso,warning",
            "fattura,fatturazione,documento",
            "cliente,anagrafica,soggetto",
            "articolo,prodotto,merce",
            "iva,imposta,aliquota",
            "contabilita,contabilità,coge",
            "magazzino,giacenza,stock",
        ]

    async def initialize(self):
        """Inizializza il client OpenSearch"""
        self.client = AsyncOpenSearch(
            hosts=[
                {
                    "host": self.settings.lexical_search.host,
                    "port": self.settings.lexical_search.port,
                }
            ],
            use_ssl=False,
            verify_certs=False,
        )

        # Crea indice se non esiste
        await self._ensure_index_exists()

        logger.info("Lexical search inizializzato")

    async def _ensure_index_exists(self):
        """Crea l'indice se non esiste"""
        try:
            exists = await self.client.indices.exists(index=self.index_name)
            if not exists:
                # Configurazione indice con analyzer italiano
                index_config = {
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                        "index": {
                            "similarity": {
                                "default": {
                                    "type": "BM25",
                                    "k1": self.settings.lexical_search.bm25_k1,
                                    "b": self.settings.lexical_search.bm25_b,
                                }
                            }
                        },
                        "analysis": {
                            "analyzer": {
                                "italian_custom": self.italian_analyzer,
                                "exact_match": {
                                    "tokenizer": "keyword",
                                    "filter": ["lowercase"],
                                },
                            },
                            "filter": {
                                "italian_stop": {
                                    "type": "stop",
                                    "stopwords": "_italian_",
                                },
                                "italian_stemmer": {
                                    "type": "stemmer",
                                    "language": "light_italian",
                                },
                                "custom_synonym": {
                                    "type": "synonym",
                                    "synonyms": self.custom_synonyms,
                                },
                            },
                        },
                    },
                    "mappings": {
                        "properties": {
                            "chunk_id": {"type": "keyword"},
                            "title": {
                                "type": "text",
                                "analyzer": "italian_custom",
                                "fields": {
                                    "exact": {
                                        "type": "text",
                                        "analyzer": "exact_match",
                                    }
                                },
                                "boost": 2.0,  # Boost per titoli
                            },
                            "content": {
                                "type": "text",
                                "analyzer": "italian_custom",
                            },
                            "breadcrumbs": {
                                "type": "text",
                                "analyzer": "italian_custom",
                                "boost": 1.5,
                            },
                            "param_name": {
                                "type": "text",
                                "analyzer": "exact_match",
                                "boost": 3.0,  # Boost alto per nomi parametri
                            },
                            "error_code": {
                                "type": "keyword",
                                "boost": 4.0,  # Boost massimo per codici errore
                            },
                            "ui_path": {
                                "type": "text",
                                "analyzer": "exact_match",
                                "boost": 2.0,
                            },
                            "content_type": {"type": "keyword"},
                            "module": {"type": "keyword"},
                            "version": {"type": "keyword"},
                            "section_level": {"type": "integer"},
                            "source_url": {"type": "keyword"},
                            "lang": {"type": "keyword"},
                            "updated_at": {"type": "date"},
                        }
                    },
                }

                await self.client.indices.create(
                    index=self.index_name,
                    body=index_config,
                )

                logger.info(f"Indice {self.index_name} creato")
            else:
                logger.info(f"Indice {self.index_name} già esistente")

        except Exception as e:
            logger.error(f"Errore creazione indice: {e}")
            raise

    async def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """
        Aggiunge chunk all'indice lessicale

        Args:
            chunks: Lista di chunk da indicizzare
        """
        if not chunks:
            return

        logger.info(f"Indicizzazione lessicale di {len(chunks)} chunk")

        # Prepara documenti per bulk insert
        actions = []
        for chunk in chunks:
            doc = self._chunk_to_document(chunk)
            action = {
                "_index": self.index_name,
                "_id": chunk.metadata.id,
                "_source": doc,
            }
            actions.append(action)

        # Bulk insert
        try:
            from opensearchpy.helpers import async_bulk

            success, failed = await async_bulk(
                self.client,
                actions,
                chunk_size=100,
                request_timeout=60,
            )

            logger.info(f"Indicizzati {success} chunk, {len(failed)} falliti")

        except Exception as e:
            logger.error(f"Errore bulk insert: {e}")
            raise

    async def search(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        boost_params: Optional[Dict[str, float]] = None,
    ) -> List[SearchResult]:
        """
        Ricerca lessicale con BM25

        Args:
            query: Query di ricerca
            top_k: Numero di risultati
            filters: Filtri sui metadati
            boost_params: Parametri di boost personalizzati

        Returns:
            Lista di risultati ordinati per rilevanza BM25
        """
        # Costruisci query OpenSearch
        search_body = self._build_search_query(query, filters, boost_params)

        try:
            response = await self.client.search(
                index=self.index_name,
                body=search_body,
                size=top_k,
            )

            # Converte risultati e popola immagini
            results = []
            for hit in response["hits"]["hits"]:
                chunk = self._document_to_chunk(hit["_source"])

                # Popola immagini se presenti
                images_data = []
                if chunk.metadata.image_ids:
                    logger.info(
                        f"Chunk {chunk.metadata.id} ha {len(chunk.metadata.image_ids)} image_ids, caricamento metadata..."
                    )
                    images_data = await self._load_images_metadata(
                        chunk.metadata.image_ids
                    )
                    logger.info(
                        f"Caricate {len(images_data)} immagini per chunk {chunk.metadata.id}"
                    )

                result = SearchResult(
                    chunk=chunk,
                    score=hit["_score"],
                    explanation=f"BM25 score: {hit['_score']:.3f}",
                    images=images_data,
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Errore ricerca lessicale: {e}")
            return []

    async def get_chunk_by_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        """Recupera chunk per ID"""
        try:
            response = await self.client.get(
                index=self.index_name,
                id=chunk_id,
            )
            return self._document_to_chunk(response["_source"])

        except Exception as e:
            logger.debug(f"Chunk {chunk_id} non trovato: {e}")
            return None

    async def delete_chunk(self, chunk_id: str) -> bool:
        """Elimina chunk per ID"""
        try:
            await self.client.delete(
                index=self.index_name,
                id=chunk_id,
            )
            return True
        except Exception as e:
            logger.error(f"Errore eliminazione chunk {chunk_id}: {e}")
            return False

    async def delete_chunks_by_url(self, source_url: str) -> int:
        """
        Elimina tutti i chunk di un URL sorgente

        Args:
            source_url: URL sorgente dei chunk da eliminare

        Returns:
            Numero di chunk eliminati
        """
        try:
            # Prima conta quanti documenti verranno eliminati
            count_query = {"query": {"term": {"source_url": source_url}}}

            count_result = await self.client.count(
                index=self.index_name, body=count_query
            )

            deleted_count = count_result.get("count", 0)

            if deleted_count > 0:
                # Elimina tutti i documenti che corrispondono
                delete_query = {"query": {"term": {"source_url": source_url}}}

                result = await self.client.delete_by_query(
                    index=self.index_name, body=delete_query
                )

                logger.info(f"Eliminati {deleted_count} chunk per URL: {source_url}")

            return deleted_count

        except Exception as e:
            logger.error(f"Errore eliminazione chunk per URL {source_url}: {e}")
            return 0

    async def get_index_stats(self) -> Dict[str, Any]:
        """Statistiche dell'indice"""
        try:
            # Aggiungo timeout specifico per evitare blocchi
            stats = await self.client.indices.stats(
                index=self.index_name,
                request_timeout=5,  # 5 secondi di timeout
            )
            index_stats = stats["indices"][self.index_name]

            return {
                "document_count": index_stats["total"]["docs"]["count"],
                "store_size": index_stats["total"]["store"]["size_in_bytes"],
                "index_health": "green",  # Semplificato
            }
        except Exception as e:
            logger.error(f"Errore recupero statistiche: {e}")
            # Ritorno valori di default invece di dizionario vuoto
            return {
                "document_count": 0,
                "store_size": 0,
                "index_health": "unknown",
                "error": str(e),
            }

    def _chunk_to_document(self, chunk: DocumentChunk) -> Dict[str, Any]:
        """Converte chunk in documento OpenSearch"""
        metadata = chunk.metadata
        return {
            "chunk_id": metadata.id,
            "title": metadata.title,
            "content": chunk.content,
            "breadcrumbs": " > ".join(metadata.breadcrumbs),
            "param_name": metadata.param_name,
            "error_code": metadata.error_code,
            "ui_path": metadata.ui_path,
            "content_type": metadata.content_type.value,
            "module": metadata.module,
            "version": metadata.version,
            "section_level": metadata.section_level,
            "source_url": metadata.source_url,
            "lang": metadata.lang,
            "updated_at": metadata.updated_at.isoformat(),
            "image_ids": metadata.image_ids or [],
        }

    def _document_to_chunk(self, doc: Dict[str, Any]) -> DocumentChunk:
        """Converte documento OpenSearch in chunk"""
        from ..core.models import ChunkMetadata, ContentType, SourceFormat
        from datetime import datetime

        metadata = ChunkMetadata(
            id=doc["chunk_id"],
            title=doc["title"],
            breadcrumbs=doc["breadcrumbs"].split(" > ")
            if doc.get("breadcrumbs")
            else [],
            section_level=doc["section_level"],
            section_path="",  # Non salvato in lexical
            content_type=ContentType(doc["content_type"]),
            version=doc["version"],
            module=doc["module"],
            param_name=doc.get("param_name"),
            ui_path=doc.get("ui_path"),
            error_code=doc.get("error_code"),
            source_url=doc["source_url"],
            source_format=SourceFormat.HTML,  # Default
            lang=doc["lang"],
            hash="",  # Non necessario per search
            updated_at=datetime.fromisoformat(doc["updated_at"]),
            image_ids=doc.get("image_ids", []),
        )

        return DocumentChunk(
            content=doc["content"],
            metadata=metadata,
        )

    async def _load_images_metadata(self, image_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Carica metadata delle immagini partendo dagli ID

        Args:
            image_ids: Lista di ID immagini (formato: {source_hash}_img_{idx} o {source_hash}_p{page}_i{idx})

        Returns:
            Lista di dizionari con metadata immagini
        """
        from pathlib import Path
        from PIL import Image

        images_data = []

        if not self.settings.image_storage.enabled:
            return images_data

        storage_base = Path(self.settings.image_storage.storage_base_path)

        for image_id in image_ids:
            try:
                # Estrai source_hash e filename dall'ID
                # Formato HTML: {source_hash}_img_{idx} -> file: img_{idx}.{ext}
                # Formato PDF: {source_hash}_p{page}_i{idx} -> file: page_{page}_img_{idx}.{ext}
                parts = image_id.split("_", 1)
                if len(parts) < 2:
                    logger.debug(f"Formato ID immagine non valido: {image_id}")
                    continue

                source_hash = parts[0]
                remaining = parts[1]

                # Determina il pattern del filename
                if remaining.startswith("img_"):
                    # Formato HTML: img_{idx}
                    idx = remaining.split("_")[1]
                    filename_pattern = f"img_{idx}"
                elif remaining.startswith("p") and "_i" in remaining:
                    # Formato PDF: p{page}_i{idx} -> page_{page}_img_{idx}
                    page_part, idx_part = remaining.split("_i", 1)
                    page_num = page_part[1:]  # Rimuove 'p'
                    filename_pattern = f"page_{int(page_num) + 1}_img_{idx_part}"
                else:
                    logger.debug(f"Formato ID immagine non riconosciuto: {image_id}")
                    continue

                # Cerca il file nella directory source_hash
                source_dir = storage_base / source_hash
                if not source_dir.exists() or not source_dir.is_dir():
                    logger.debug(
                        f"Directory {source_hash} non trovata per immagine {image_id}"
                    )
                    continue

                # Cerca file con questo pattern (diversi formati possibili)
                found = False
                for ext in ["png", "jpg", "jpeg", "gif", "webp"]:
                    image_file = source_dir / f"{filename_pattern}.{ext}"
                    if image_file.exists():
                        # Ricostruisci metadata base dall'immagine
                        try:
                            with Image.open(image_file) as img:
                                width, height = img.size
                                format_name = img.format.lower() if img.format else ext

                            image_data = {
                                "id": image_id,
                                "storage_path": str(image_file),
                                "image_url": f"/images/{source_dir.name}/{image_file.name}",
                                "width": width,
                                "height": height,
                                "format": format_name,
                                "file_size_bytes": image_file.stat().st_size,
                            }
                            images_data.append(image_data)
                            found = True
                            break
                        except Exception as img_err:
                            logger.warning(
                                f"Errore lettura immagine {image_file}: {img_err}"
                            )

                if not found:
                    logger.debug(
                        f"Immagine {image_id} non trovata nel filesystem (pattern: {filename_pattern})"
                    )

            except Exception as e:
                logger.warning(f"Errore caricamento metadata immagine {image_id}: {e}")
                continue

        return images_data

    def _build_search_query(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        boost_params: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Costruisce query OpenSearch"""
        # Boost di default
        default_boosts = {
            "title": self.settings.retrieval.title_boost,
            "breadcrumbs": self.settings.retrieval.breadcrumbs_boost,
            "param_name": self.settings.retrieval.param_name_boost,
            "error_code": self.settings.retrieval.error_code_boost,
        }

        if boost_params:
            default_boosts.update(boost_params)

        # Query multi-field con boost
        multi_match = {
            "multi_match": {
                "query": query,
                "fields": [
                    f"title^{default_boosts['title']}",
                    f"content",
                    f"breadcrumbs^{default_boosts['breadcrumbs']}",
                    f"param_name^{default_boosts['param_name']}",
                    f"ui_path^1.5",
                ],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        }

        # Query per codici errore (exact match)
        error_code_query = {
            "term": {
                "error_code": {
                    "value": query.upper(),
                    "boost": default_boosts["error_code"],
                }
            }
        }

        # Combina query
        bool_query = {
            "bool": {
                "should": [multi_match, error_code_query],
                "minimum_should_match": 1,
            }
        }

        # Aggiungi filtri
        if filters:
            filter_clauses = []
            for field, value in filters.items():
                if value:
                    filter_clauses.append({"term": {field: value}})

            if filter_clauses:
                bool_query["bool"]["filter"] = filter_clauses

        # Query body (BM25 viene configurato a livello di indice)
        search_body = {
            "query": bool_query,
        }

        return search_body

    async def close(self):
        """Chiude connessione"""
        if self.client:
            await self.client.close()
        logger.info("Lexical search chiuso")
