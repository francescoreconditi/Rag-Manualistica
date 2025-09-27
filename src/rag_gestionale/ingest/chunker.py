"""
Sistema di chunking intelligente per manuali di gestionali.
Implementa strategia parent/child con overlap controllato e metadati ricchi.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from ..core.models import DocumentChunk, ChunkMetadata, ContentType
from ..core.utils import (
    estimate_tokens,
    split_into_sentences,
    truncate_to_tokens,
    normalize_text,
)
from ..config.settings import get_settings


@dataclass
class ChunkingContext:
    """Contesto per il chunking di un documento"""

    document_title: str
    module: str
    version: str
    source_url: str
    total_chunks: int = 0
    parent_chunk_id: Optional[str] = None


class IntelligentChunker:
    """Chunker intelligente per documenti di gestionali"""

    def __init__(self):
        self.settings = get_settings()

        # Pattern per riconoscere confini naturali
        self.section_boundaries = [
            r"^\d+\.\s+",  # 1. Sezione numerata
            r"^\d+\.\d+\s+",  # 1.1 Sottosezione
            r"^[A-Z]{1,3}\.\s+",  # A. Appendice
            r"^Procedura\s*:",  # Procedura:
            r"^Parametro\s*:",  # Parametro:
            r"^Attenzione\s*[:!]",  # Attenzione:
            r"^Nota\s*[:!]",  # Nota:
            r"^Esempio\s*:",  # Esempio:
        ]

        # Indicatori di fine chunk
        self.chunk_endings = [
            r"\n\s*---+\s*\n",  # Linea divisoria
            r"\n\s*Vedi anche:",  # Collegamenti
            r"\n\s*Per ulteriori",  # Riferimenti
        ]

        # Pattern per step procedurali
        self.step_patterns = [
            r"^\d+\)\s+",  # 1) Step
            r"^-\s+",  # - Step
            r"^•\s+",  # • Step
            r"^Step\s+\d+",  # Step 1
            r"^Passo\s+\d+",  # Passo 1
        ]

    def chunk_document(
        self, document: DocumentChunk, context: ChunkingContext
    ) -> List[DocumentChunk]:
        """
        Chunking principale di un documento

        Args:
            document: Documento da dividere
            context: Contesto del chunking

        Returns:
            Lista di chunk processati con gerarchia parent/child
        """
        chunks = []

        # Classifica il tipo di contenuto per strategia appropriata
        content_type = document.metadata.content_type

        if content_type == ContentType.PROCEDURE:
            chunks = self._chunk_procedure(document, context)
        elif content_type == ContentType.PARAMETER:
            chunks = self._chunk_parameter(document, context)
        elif content_type == ContentType.TABLE:
            chunks = self._chunk_table(document, context)
        elif content_type == ContentType.ERROR:
            chunks = self._chunk_error(document, context)
        else:
            # Contenuto generico - usa chunking adattivo
            chunks = self._chunk_adaptive(document, context)

        # Post-processing: aggiungi overlap e metadati finali
        chunks = self._add_overlap_and_finalize(chunks, context)

        return chunks

    def _chunk_procedure(
        self, document: DocumentChunk, context: ChunkingContext
    ) -> List[DocumentChunk]:
        """Chunking specializzato per procedure"""
        chunks = []
        content = document.content

        # Prima crea un parent chunk con l'intera procedura (se non troppo grande)
        parent_tokens = estimate_tokens(content)

        if parent_tokens <= self.settings.chunking.parent_max_tokens:
            # Documento piccolo - un solo chunk parent
            parent_chunk = self._create_chunk(
                content=content,
                chunk_type="parent",
                original_metadata=document.metadata,
                context=context,
                chunk_index=0,
            )
            chunks.append(parent_chunk)
        else:
            # Documento grande - dividi in parent + child
            parent_content = self._create_summary_for_parent(content)
            parent_chunk = self._create_chunk(
                content=parent_content,
                chunk_type="parent",
                original_metadata=document.metadata,
                context=context,
                chunk_index=0,
            )
            chunks.append(parent_chunk)

            # Crea child chunks per singoli step
            child_chunks = self._split_into_steps(
                content, document.metadata, context, parent_chunk.metadata.id
            )
            chunks.extend(child_chunks)

        return chunks

    def _chunk_parameter(
        self, document: DocumentChunk, context: ChunkingContext
    ) -> List[DocumentChunk]:
        """Chunking per parametri - generalmente atomici"""
        content = document.content
        content_tokens = estimate_tokens(content)

        # I parametri sono generalmente atomici, no overlap
        if content_tokens <= self.settings.chunking.child_param_max_tokens:
            # Un solo chunk
            chunk = self._create_chunk(
                content=content,
                chunk_type="parameter",
                original_metadata=document.metadata,
                context=context,
                chunk_index=0,
            )
            return [chunk]
        else:
            # Parametro molto lungo - dividi per paragrafi logici
            paragraphs = self._split_by_paragraphs(content)
            chunks = []

            for i, paragraph in enumerate(paragraphs):
                if len(paragraph.strip()) > 20:  # Filtro paragrafi troppo corti
                    chunk = self._create_chunk(
                        content=paragraph,
                        chunk_type="parameter",
                        original_metadata=document.metadata,
                        context=context,
                        chunk_index=i,
                    )
                    chunks.append(chunk)

            return chunks

    def _chunk_table(
        self, document: DocumentChunk, context: ChunkingContext
    ) -> List[DocumentChunk]:
        """Chunking per tabelle"""
        content = document.content
        lines = content.split("\n")

        # Identifica righe di tabella
        table_rows = [line for line in lines if "|" in line and "---" not in line]

        max_rows = self.settings.chunking.table_max_rows
        if len(table_rows) <= max_rows:
            # Tabella piccola - un chunk
            chunk = self._create_chunk(
                content=content,
                chunk_type="table",
                original_metadata=document.metadata,
                context=context,
                chunk_index=0,
            )
            return [chunk]
        else:
            # Tabella grande - dividi mantenendo header
            chunks = []
            header_lines = []

            # Trova header
            for line in lines:
                if "---" in line:
                    break
                header_lines.append(line)

            # Dividi righe dati
            data_rows = table_rows[len(header_lines) :]
            for i in range(0, len(data_rows), max_rows):
                chunk_rows = header_lines + data_rows[i : i + max_rows]
                chunk_content = "\n".join(chunk_rows)

                chunk = self._create_chunk(
                    content=chunk_content,
                    chunk_type="table",
                    original_metadata=document.metadata,
                    context=context,
                    chunk_index=i // max_rows,
                )
                chunks.append(chunk)

            return chunks

    def _chunk_error(
        self, document: DocumentChunk, context: ChunkingContext
    ) -> List[DocumentChunk]:
        """Chunking per errori - solitamente atomici"""
        content = document.content

        # Gli errori sono generalmente brevi e atomici
        chunk = self._create_chunk(
            content=content,
            chunk_type="error",
            original_metadata=document.metadata,
            context=context,
            chunk_index=0,
        )
        return [chunk]

    def _chunk_adaptive(
        self, document: DocumentChunk, context: ChunkingContext
    ) -> List[DocumentChunk]:
        """Chunking adattivo per contenuto generico"""
        content = document.content
        content_tokens = estimate_tokens(content)

        if content_tokens <= self.settings.chunking.parent_max_tokens:
            # Contenuto piccolo - un chunk
            chunk = self._create_chunk(
                content=content,
                chunk_type="concept",
                original_metadata=document.metadata,
                context=context,
                chunk_index=0,
            )
            return [chunk]
        else:
            # Contenuto grande - dividi su confini naturali
            return self._split_on_natural_boundaries(document, context)

    def _split_into_steps(
        self,
        content: str,
        original_metadata: ChunkMetadata,
        context: ChunkingContext,
        parent_id: str,
    ) -> List[DocumentChunk]:
        """Divide contenuto procedurale in step"""
        chunks = []
        lines = content.split("\n")

        current_step = []
        step_number = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Verifica se è un nuovo step
            is_step_start = any(
                re.match(pattern, line) for pattern in self.step_patterns
            )

            if is_step_start and current_step:
                # Finalizza step precedente
                step_content = "\n".join(current_step)
                if len(step_content) > 30:  # Minimo contenuto
                    chunk = self._create_chunk(
                        content=step_content,
                        chunk_type="step",
                        original_metadata=original_metadata,
                        context=context,
                        chunk_index=step_number,
                        parent_id=parent_id,
                    )
                    chunks.append(chunk)
                    step_number += 1

                current_step = [line]
            else:
                current_step.append(line)

        # Ultimo step
        if current_step:
            step_content = "\n".join(current_step)
            if len(step_content) > 30:
                chunk = self._create_chunk(
                    content=step_content,
                    chunk_type="step",
                    original_metadata=original_metadata,
                    context=context,
                    chunk_index=step_number,
                    parent_id=parent_id,
                )
                chunks.append(chunk)

        return chunks

    def _split_on_natural_boundaries(
        self, document: DocumentChunk, context: ChunkingContext
    ) -> List[DocumentChunk]:
        """Divide su confini naturali (paragrafi, sezioni)"""
        content = document.content
        max_tokens = self.settings.chunking.parent_max_tokens

        # Dividi in paragrafi
        paragraphs = self._split_by_paragraphs(content)

        chunks = []
        current_chunk = []
        current_tokens = 0

        for paragraph in paragraphs:
            para_tokens = estimate_tokens(paragraph)

            if current_tokens + para_tokens > max_tokens and current_chunk:
                # Finalizza chunk corrente
                chunk_content = "\n\n".join(current_chunk)
                chunk = self._create_chunk(
                    content=chunk_content,
                    chunk_type="concept",
                    original_metadata=document.metadata,
                    context=context,
                    chunk_index=len(chunks),
                )
                chunks.append(chunk)

                current_chunk = [paragraph]
                current_tokens = para_tokens
            else:
                current_chunk.append(paragraph)
                current_tokens += para_tokens

        # Ultimo chunk
        if current_chunk:
            chunk_content = "\n\n".join(current_chunk)
            chunk = self._create_chunk(
                content=chunk_content,
                chunk_type="concept",
                original_metadata=document.metadata,
                context=context,
                chunk_index=len(chunks),
            )
            chunks.append(chunk)

        return chunks

    def _split_by_paragraphs(self, content: str) -> List[str]:
        """Divide contenuto in paragrafi logici"""
        # Divide su doppio newline
        paragraphs = re.split(r"\n\s*\n", content)

        # Filtra paragrafi vuoti e troppo corti
        filtered = []
        for para in paragraphs:
            para = para.strip()
            if len(para) > 20:  # Minimo 20 caratteri
                filtered.append(para)

        return filtered

    def _create_summary_for_parent(self, content: str) -> str:
        """Crea summary estrattivo per chunk parent"""
        sentences = split_into_sentences(content)

        # Prendi prime 2-3 frasi + ultima frase (se utile)
        summary_sentences = sentences[:3]
        if len(sentences) > 5:
            last_sentence = sentences[-1]
            if len(last_sentence) > 20 and "vedi" not in last_sentence.lower():
                summary_sentences.append(last_sentence)

        summary = " ".join(summary_sentences)

        # Tronca se troppo lungo
        max_tokens = self.settings.chunking.parent_max_tokens // 2
        return truncate_to_tokens(summary, max_tokens)

    def _create_chunk(
        self,
        content: str,
        chunk_type: str,
        original_metadata: ChunkMetadata,
        context: ChunkingContext,
        chunk_index: int,
        parent_id: Optional[str] = None,
    ) -> DocumentChunk:
        """Crea un nuovo chunk con metadati appropriati"""

        # ID chunk basato su contesto + indice
        chunk_id = f"{original_metadata.id}_chunk_{chunk_index:03d}"
        if parent_id:
            chunk_id = f"{parent_id}_child_{chunk_index:03d}"

        # Copia metadati originali e aggiorna
        new_metadata = ChunkMetadata(
            id=chunk_id,
            title=original_metadata.title,
            breadcrumbs=original_metadata.breadcrumbs,
            section_level=original_metadata.section_level,
            section_path=original_metadata.section_path,
            content_type=original_metadata.content_type,
            version=original_metadata.version,
            module=original_metadata.module,
            param_name=original_metadata.param_name,
            ui_path=original_metadata.ui_path,
            error_code=original_metadata.error_code,
            source_url=original_metadata.source_url,
            source_format=original_metadata.source_format,
            page_range=original_metadata.page_range,
            anchor=original_metadata.anchor,
            lang=original_metadata.lang,
            hash=original_metadata.hash,  # Verrà aggiornato dopo
            updated_at=original_metadata.updated_at,
            parent_chunk_id=parent_id,
        )

        # Aggiorna hash con contenuto effettivo
        from ..core.utils import compute_content_hash

        new_metadata.hash = compute_content_hash(content)

        return DocumentChunk(content=normalize_text(content), metadata=new_metadata)

    def _add_overlap_and_finalize(
        self, chunks: List[DocumentChunk], context: ChunkingContext
    ) -> List[DocumentChunk]:
        """Aggiunge overlap tra chunk consecutivi"""
        if len(chunks) <= 1:
            return chunks

        # Configura overlap basato sul tipo
        overlap_tokens = self._get_overlap_tokens(chunks[0].metadata.content_type)

        if overlap_tokens == 0:
            return chunks  # No overlap per parametri

        finalized_chunks = [chunks[0]]  # Primo chunk senza overlap

        for i in range(1, len(chunks)):
            current_chunk = chunks[i]
            previous_chunk = chunks[i - 1]

            # Estrai overlap dal chunk precedente
            prev_sentences = split_into_sentences(previous_chunk.content)
            overlap_content = ""

            # Prendi ultime frasi fino al limite di token
            current_tokens = 0
            for sentence in reversed(prev_sentences):
                sentence_tokens = estimate_tokens(sentence)
                if current_tokens + sentence_tokens <= overlap_tokens:
                    overlap_content = sentence + " " + overlap_content
                    current_tokens += sentence_tokens
                else:
                    break

            # Aggiungi overlap al chunk corrente
            if overlap_content.strip():
                new_content = f"[...continua] {overlap_content.strip()}\n\n{current_chunk.content}"
                current_chunk.content = new_content

            finalized_chunks.append(current_chunk)

        return finalized_chunks

    def _get_overlap_tokens(self, content_type: ContentType) -> int:
        """Ottiene token di overlap basati sul tipo di contenuto"""
        if content_type == ContentType.PARAMETER:
            return self.settings.chunking.child_param_overlap_tokens
        elif content_type == ContentType.PROCEDURE:
            return self.settings.chunking.child_proc_overlap_tokens
        else:
            return self.settings.chunking.parent_overlap_tokens


# Utility function per chunking rapido
def chunk_documents(documents: List[DocumentChunk]) -> List[DocumentChunk]:
    """
    Utility per chunking rapido di documenti

    Args:
        documents: Lista di documenti da dividere

    Returns:
        Lista di chunk processati
    """
    chunker = IntelligentChunker()
    all_chunks = []

    for doc in documents:
        context = ChunkingContext(
            document_title=doc.metadata.title,
            module=doc.metadata.module,
            version=doc.metadata.version,
            source_url=doc.metadata.source_url,
        )

        chunks = chunker.chunk_document(doc, context)
        all_chunks.extend(chunks)

    return all_chunks
