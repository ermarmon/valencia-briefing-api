"""
cache_store.py — Caché JSON persistente en /data/briefing_cache.json.

Por qué en /data y no en memoria:
  - /data persiste entre reinicios del add-on (mapeado por el Supervisor).
  - Si HA reinicia el contenedor, el primer GET ya puede responder con
    datos del ciclo anterior sin esperar a que los feeds respondan.
  - En memoria se perdería al reiniciar.

Invalidación:
  - Automática: el campo "expires_at" en el JSON se compara con now().
  - Manual: GET /refresh borra el archivo de caché.
  - Regeneración: siempre que expires_at < now() o el archivo no exista.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .settings import CACHE_FILE_PATH, CACHE_TTL_MINUTES

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load() -> dict | None:
    """
    Lee la caché del disco.
    Devuelve el dict si existe y no ha expirado, None en caso contrario.
    """
    if not CACHE_FILE_PATH.exists():
        logger.debug("Caché no encontrada en disco (%s)", CACHE_FILE_PATH)
        return None

    try:
        data = json.loads(CACHE_FILE_PATH.read_text(encoding="utf-8"))
        expires_at_str = data.get("expires_at", "")
        if not expires_at_str:
            return None

        expires_at = datetime.fromisoformat(expires_at_str)
        if datetime.now(timezone.utc) > expires_at:
            logger.info("Caché expirada (expires_at=%s)", expires_at_str)
            return None

        logger.info("Caché válida hasta %s", expires_at_str)
        return data

    except Exception as exc:
        logger.warning("Error leyendo caché: %s — regenerando", exc)
        return None


def save(briefing_dict: dict) -> None:
    """
    Guarda el briefing en disco añadiendo expires_at.
    Si /data no existe (desarrollo local) usa /tmp.
    """
    path = CACHE_FILE_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        path = Path("/tmp/briefing_cache.json")
        logger.warning("No se pudo crear %s — usando %s", CACHE_FILE_PATH, path)

    expires_at = datetime.now(timezone.utc)
    from datetime import timedelta
    expires_at += timedelta(minutes=CACHE_TTL_MINUTES)

    payload = {
        **briefing_dict,
        "cached": True,
        "expires_at": expires_at.isoformat(),
        "cache_ttl_minutes": CACHE_TTL_MINUTES,
    }

    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Caché guardada en %s (expira %s)", path, expires_at.isoformat())
    except Exception as exc:
        logger.error("Error guardando caché: %s", exc)


def invalidate() -> None:
    """Elimina el archivo de caché del disco."""
    if CACHE_FILE_PATH.exists():
        try:
            CACHE_FILE_PATH.unlink()
            logger.info("Caché invalidada: %s eliminado", CACHE_FILE_PATH)
        except Exception as exc:
            logger.error("Error eliminando caché: %s", exc)
    else:
        logger.debug("invalidate() llamado pero no había caché en disco")
