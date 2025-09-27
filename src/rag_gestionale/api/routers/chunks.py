"""
Router per gli endpoint di gestione chunks.
"""

from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_components, RAGComponents


router = APIRouter(prefix="/chunks", tags=["chunks"])


@router.get("/{chunk_id}")
async def get_chunk(
    chunk_id: str, components: RAGComponents = Depends(get_components)
) -> Dict[str, Any]:
    """Recupera un chunk specifico"""
    try:
        chunk = await components.retriever.get_chunk_by_id(chunk_id)

        if not chunk:
            raise HTTPException(status_code=404, detail="Chunk non trovato")

        return {
            "id": chunk.metadata.id,
            "title": chunk.metadata.title,
            "content": chunk.content,
            "metadata": {
                "module": chunk.metadata.module,
                "version": chunk.metadata.version,
                "content_type": chunk.metadata.content_type.value,
                "source_url": chunk.metadata.source_url,
                "updated_at": chunk.metadata.updated_at.isoformat(),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore recupero chunk: {str(e)}")


@router.delete("/{chunk_id}")
async def delete_chunk(
    chunk_id: str, components: RAGComponents = Depends(get_components)
) -> Dict[str, str]:
    """Elimina un chunk specifico"""
    try:
        success = await components.retriever.delete_chunk(chunk_id)

        if success:
            return {"status": "success", "message": f"Chunk {chunk_id} eliminato"}
        else:
            raise HTTPException(status_code=404, detail="Chunk non trovato")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Errore eliminazione chunk: {str(e)}"
        )
