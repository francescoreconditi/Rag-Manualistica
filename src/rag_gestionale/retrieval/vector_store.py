"""
Vector store con Qdrant per embeddings densi.
Ottimizzato per performance e filtri ricchi su metadati.
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    CreateCollection,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
)
from loguru import logger
from sentence_transformers import SentenceTransformer

from ..core.models import DocumentChunk, SearchResult
from ..config.settings import get_settings


class VectorStore:
    """Vector store usando Qdrant per embeddings densi"""

    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[QdrantClient] = None
        self.async_client: Optional[AsyncQdrantClient] = None
        self.embedding_model: Optional[SentenceTransformer] = None
        self.collection_name = self.settings.vector_store.collection_name

    async def initialize(self):
        """Inizializza il vector store"""
        # Client Qdrant
        self.client = QdrantClient(
            host=self.settings.vector_store.host,
            port=self.settings.vector_store.port,
            check_compatibility=False,
        )

        self.async_client = AsyncQdrantClient(
            host=self.settings.vector_store.host,
            port=self.settings.vector_store.port,
            check_compatibility=False,
        )

        # Modello embedding
        logger.info(
            f"Caricamento modello embedding: {self.settings.embedding.model_name}"
        )
        self.embedding_model = SentenceTransformer(
            self.settings.embedding.model_name,
            device="cpu",  # Usa GPU se disponibile
        )

        # Crea collection se non esiste
        await self._ensure_collection_exists()

        logger.info("Vector store inizializzato")

    async def _ensure_collection_exists(self):
        """Crea la collection se non esiste"""
        try:
            collection_info = await self.async_client.get_collection(
                self.collection_name
            )
            logger.info(f"Collection {self.collection_name} già esistente")
        except Exception:
            # Collection non esiste, creala
            vector_size = self.embedding_model.get_sentence_embedding_dimension()

            await self.async_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                    hnsw_config=models.HnswConfigDiff(
                        m=self.settings.vector_store.hnsw_m,
                        ef_construct=self.settings.vector_store.hnsw_ef_construct,
                    ),
                ),
                optimizers_config=models.OptimizersConfigDiff(
                    default_segment_number=2,
                ),
            )

            logger.info(f"Collection {self.collection_name} creata")

    async def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """
        Aggiunge chunk al vector store

        Args:
            chunks: Lista di chunk da indicizzare
        """
        if not chunks:
            return

        logger.info(f"Indicizzazione di {len(chunks)} chunk")

        try:
            # Genera embeddings in batch
            texts = [chunk.content for chunk in chunks]
            logger.debug(f"Generazione embeddings per {len(texts)} testi")
            embeddings = await self._generate_embeddings_batch(texts)
            logger.debug(f"Embeddings generati: {len(embeddings)}")

            # Prepara punti per Qdrant
            points = []
            for i, chunk in enumerate(chunks):
                point = PointStruct(
                    id=abs(
                        hash(chunk.metadata.id)
                    ),  # Usa hash positivo come ID numerico
                    vector=embeddings[i].tolist(),
                    payload=self._chunk_to_payload(chunk),
                )
                points.append(point)

            logger.debug(f"Preparati {len(points)} punti per l'inserimento")

            # Inserisci in batch
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                logger.debug(
                    f"Inserimento batch {i // batch_size + 1}: {len(batch)} punti"
                )
                await self.async_client.upsert(
                    collection_name=self.collection_name,
                    points=batch,
                )

            logger.info(f"Indicizzati {len(chunks)} chunk nel vector store")
        except Exception as e:
            logger.error(f"ERRORE durante indicizzazione nel vector store: {e}")
            raise

    async def delete_chunks_by_url(self, source_url: str) -> int:
        """
        Elimina tutti i chunk di un URL sorgente

        Args:
            source_url: URL sorgente dei chunk da eliminare

        Returns:
            Numero di chunk eliminati
        """
        try:
            # Crea filtro per source_url
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="source_url",
                        match=MatchValue(value=source_url),
                    )
                ]
            )

            # Prima conta quanti chunk verranno eliminati
            count_result = await self.async_client.count(
                collection_name=self.collection_name,
                count_filter=filter_condition,
                exact=True,
            )

            deleted_count = count_result.count

            if deleted_count > 0:
                # Elimina tutti i punti che corrispondono al filtro
                await self.async_client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.FilterSelector(filter=filter_condition),
                )
                logger.info(f"Eliminati {deleted_count} chunk per URL: {source_url}")

            return deleted_count

        except Exception as e:
            logger.error(f"Errore eliminazione chunk per URL {source_url}: {e}")
            return 0

    async def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0,
    ) -> List[SearchResult]:
        """
        Ricerca semantica nel vector store

        Args:
            query: Query di ricerca
            top_k: Numero di risultati
            filters: Filtri sui metadati
            score_threshold: Soglia minima di score

        Returns:
            Lista di risultati ordinati per rilevanza
        """
        # Genera embedding della query
        query_embedding = await self._generate_embedding(query)

        # Costruisci filtri Qdrant
        qdrant_filter = self._build_filter(filters) if filters else None

        # Esegui ricerca
        search_result = await self.async_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding.tolist(),
            limit=top_k,
            query_filter=qdrant_filter,
            score_threshold=score_threshold,
            with_payload=True,
        )

        # Converte risultati e popola immagini
        results = []
        for hit in search_result:
            chunk = self._payload_to_chunk(hit.payload)

            # Popola immagini se presenti
            images_data = []
            if chunk.metadata.image_ids:
                logger.info(
                    f"Chunk {chunk.metadata.id} ha {len(chunk.metadata.image_ids)} image_ids, caricamento metadata..."
                )
                images_data = await self._load_images_metadata(chunk.metadata.image_ids)
                logger.info(
                    f"Caricate {len(images_data)} immagini per chunk {chunk.metadata.id}"
                )

            result = SearchResult(
                chunk=chunk,
                score=hit.score,
                explanation=f"Vector similarity: {hit.score:.3f}",
                images=images_data,
            )
            results.append(result)

        return results

    async def get_chunk_by_id(self, chunk_id: str) -> Optional[DocumentChunk]:
        """Recupera chunk per ID"""
        try:
            point = await self.async_client.retrieve(
                collection_name=self.collection_name,
                ids=[hash(chunk_id)],
                with_payload=True,
            )

            if point:
                return self._payload_to_chunk(point[0].payload)
            return None

        except Exception as e:
            logger.error(f"Errore recupero chunk {chunk_id}: {e}")
            return None

    async def delete_chunk(self, chunk_id: str) -> bool:
        """Elimina chunk per ID"""
        try:
            await self.async_client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(points=[hash(chunk_id)]),
            )
            return True
        except Exception as e:
            logger.error(f"Errore eliminazione chunk {chunk_id}: {e}")
            return False

    async def update_chunk(self, chunk: DocumentChunk) -> bool:
        """Aggiorna chunk esistente"""
        try:
            # Elimina vecchio
            await self.delete_chunk(chunk.metadata.id)
            # Inserisci nuovo
            await self.add_chunks([chunk])
            return True
        except Exception as e:
            logger.error(f"Errore aggiornamento chunk {chunk.metadata.id}: {e}")
            return False

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Statistiche della collection"""
        try:
            info = await self.async_client.get_collection(self.collection_name)
            return {
                "total_points": info.points_count,
                "vector_size": info.config.params.vectors.size,
                "distance": info.config.params.vectors.distance,
                "status": info.status,
            }
        except Exception as e:
            logger.error(f"Errore recupero statistiche: {e}")
            return {}

    async def _generate_embeddings_batch(self, texts: List[str]) -> List:
        """Genera embeddings in batch per efficienza"""
        import time

        start = time.time()
        logger.debug(f"Inizio generazione embeddings per {len(texts)} testi")

        # Esegui in thread pool per non bloccare async loop
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.embedding_model.encode(
                texts,
                batch_size=self.settings.embedding.batch_size,
                normalize_embeddings=self.settings.embedding.normalize_embeddings,
                show_progress_bar=False,
            ),
        )

        elapsed = time.time() - start
        logger.debug(f"Embeddings generati in {elapsed:.2f}s")
        return embeddings

    async def _generate_embedding(self, text: str):
        """Genera embedding per singolo testo"""
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self.embedding_model.encode(
                [text],
                normalize_embeddings=self.settings.embedding.normalize_embeddings,
            )[0],
        )
        return embedding

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

    def _chunk_to_payload(self, chunk: DocumentChunk) -> Dict[str, Any]:
        """Converte chunk in payload Qdrant"""
        metadata = chunk.metadata

        # Crea payload base
        payload = {
            "chunk_id": metadata.id,
            "title": metadata.title,
            "content": chunk.content,
            "breadcrumbs": metadata.breadcrumbs or [],
            "section_level": metadata.section_level,
            "section_path": metadata.section_path,
            "content_type": metadata.content_type.value,
            "version": metadata.version,
            "module": metadata.module,
            "source_url": metadata.source_url,
            "source_format": metadata.source_format.value,
            "lang": metadata.lang or "it",
            "hash": metadata.hash,
            "updated_at": metadata.updated_at.isoformat(),
        }

        # Aggiungi campi opzionali solo se non None
        if metadata.param_name:
            payload["param_name"] = metadata.param_name
        if metadata.ui_path:
            payload["ui_path"] = metadata.ui_path
        if metadata.error_code:
            payload["error_code"] = metadata.error_code
        if metadata.page_range:
            payload["page_range"] = metadata.page_range
        if metadata.anchor:
            payload["anchor"] = metadata.anchor
        if metadata.parent_chunk_id:
            payload["parent_chunk_id"] = metadata.parent_chunk_id
        if metadata.child_chunk_ids:
            payload["child_chunk_ids"] = metadata.child_chunk_ids
        if metadata.image_ids:
            payload["image_ids"] = metadata.image_ids

        return payload

    def _payload_to_chunk(self, payload: Dict[str, Any]) -> DocumentChunk:
        """Converte payload Qdrant in chunk"""
        from ..core.models import ChunkMetadata, ContentType, SourceFormat

        # Ricostruisci metadati
        metadata = ChunkMetadata(
            id=payload["chunk_id"],
            title=payload["title"],
            breadcrumbs=payload.get("breadcrumbs", []),
            section_level=payload["section_level"],
            section_path=payload["section_path"],
            content_type=ContentType(payload["content_type"]),
            version=payload["version"],
            module=payload["module"],
            param_name=payload.get("param_name"),
            ui_path=payload.get("ui_path"),
            error_code=payload.get("error_code"),
            source_url=payload["source_url"],
            source_format=SourceFormat(payload["source_format"]),
            page_range=payload.get("page_range"),
            anchor=payload.get("anchor"),
            lang=payload["lang"],
            hash=payload["hash"],
            updated_at=datetime.fromisoformat(payload["updated_at"]),
            parent_chunk_id=payload.get("parent_chunk_id"),
            child_chunk_ids=payload.get("child_chunk_ids", []),
            image_ids=payload.get("image_ids", []),
        )

        return DocumentChunk(
            content=payload["content"],
            metadata=metadata,
        )

    def _build_filter(self, filters: Dict[str, Any]) -> Filter:
        """Costruisce filtro Qdrant da dizionario"""
        conditions = []

        for field, value in filters.items():
            if field == "module" and value:
                conditions.append(
                    FieldCondition(
                        key="module",
                        match=MatchValue(value=value),
                    )
                )
            elif field == "version" and value:
                conditions.append(
                    FieldCondition(
                        key="version",
                        match=MatchValue(value=value),
                    )
                )
            elif field == "content_type" and value:
                conditions.append(
                    FieldCondition(
                        key="content_type",
                        match=MatchValue(value=value),
                    )
                )
            elif field == "section_level" and isinstance(value, dict):
                # Range query per livello sezione
                conditions.append(
                    FieldCondition(
                        key="section_level",
                        range=Range(
                            gte=value.get("min"),
                            lte=value.get("max"),
                        ),
                    )
                )

        return Filter(must=conditions) if conditions else None

    async def close(self):
        """Chiude connessioni"""
        if self.async_client:
            await self.async_client.close()
        if self.client:
            self.client.close()
        logger.info("Vector store chiuso")
