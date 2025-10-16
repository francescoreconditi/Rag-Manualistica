"""
Router API per servire immagini estratte dai documenti.
Fornisce endpoint per accesso diretto alle immagini e metadata.
"""

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from loguru import logger

from ...config.settings import get_settings

router = APIRouter(prefix="/images", tags=["images"])

# Configurazione storage
settings = get_settings()
STORAGE_BASE = Path(settings.image_storage.storage_base_path)


@router.get("/{source_hash}/{filename}")
async def get_image(source_hash: str, filename: str):
    """
    Serve un'immagine dal filesystem

    Args:
        source_hash: Hash del documento sorgente
        filename: Nome del file immagine

    Returns:
        File immagine
    """
    try:
        image_path = STORAGE_BASE / source_hash / filename

        if not image_path.exists():
            logger.warning(f"Immagine non trovata: {image_path}")
            raise HTTPException(status_code=404, detail="Immagine non trovata")

        # Verifica che il file sia nell'area storage (security)
        if not str(image_path.resolve()).startswith(str(STORAGE_BASE.resolve())):
            logger.error(f"Tentativo di accesso a path non autorizzato: {image_path}")
            raise HTTPException(status_code=403, detail="Accesso negato")

        logger.debug(f"Servendo immagine: {image_path}")
        return FileResponse(
            image_path,
            media_type=f"image/{image_path.suffix.lstrip('.')}",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore servendo immagine {source_hash}/{filename}: {e}")
        raise HTTPException(status_code=500, detail="Errore interno del server")


@router.get("/info/{source_hash}")
async def list_images_by_source(
    source_hash: str,
) -> Dict[str, List[Dict[str, str]]]:
    """
    Elenca tutte le immagini per un documento sorgente

    Args:
        source_hash: Hash del documento sorgente

    Returns:
        Lista di metadati immagini
    """
    try:
        source_dir = STORAGE_BASE / source_hash

        if not source_dir.exists() or not source_dir.is_dir():
            raise HTTPException(
                status_code=404, detail="Nessuna immagine trovata per questo documento"
            )

        images = []
        for img_file in source_dir.iterdir():
            if img_file.is_file():
                images.append(
                    {
                        "filename": img_file.name,
                        "url": f"/images/{source_hash}/{img_file.name}",
                        "size_bytes": img_file.stat().st_size,
                        "format": img_file.suffix.lstrip("."),
                    }
                )

        return {"source_hash": source_hash, "images": images, "total": len(images)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore recuperando lista immagini per {source_hash}: {e}")
        raise HTTPException(status_code=500, detail="Errore interno del server")


@router.get("/storage/stats")
async def get_storage_stats() -> Dict[str, Any]:
    """
    Statistiche generali sullo storage immagini

    Returns:
        Statistiche storage (totale immagini, dimensione, etc.)
    """
    try:
        if not STORAGE_BASE.exists():
            return {
                "total_images": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "total_sources": 0,
            }

        total_images = 0
        total_size = 0
        total_sources = 0

        for source_dir in STORAGE_BASE.iterdir():
            if source_dir.is_dir():
                total_sources += 1
                for img_file in source_dir.iterdir():
                    if img_file.is_file():
                        total_images += 1
                        total_size += img_file.stat().st_size

        return {
            "total_images": total_images,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_sources": total_sources,
            "storage_path": str(STORAGE_BASE),
        }

    except Exception as e:
        logger.error(f"Errore recuperando statistiche storage: {e}")
        raise HTTPException(status_code=500, detail="Errore interno del server")
