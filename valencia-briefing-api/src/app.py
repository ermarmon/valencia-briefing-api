"""
app.py — Valencia Briefing API v2.0.0

Endpoints:
  GET  /                    → healthcheck con versión y opciones activas
  GET  /valencia_briefing   → briefing completo (con caché persistente)
  GET  /refresh             → fuerza regeneración invalidando caché
  GET  /debug               → igual que /valencia_briefing pero con info de fuentes
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import cache_store, pipeline
from .settings import CACHE_TTL_MINUTES, LOG_LEVEL, MAX_AGE_HOURS, MAX_ITEMS, OPTIONS

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Valencia Briefing API",
    version="2.0.0",
    description="Agregador local de noticias y eventos de Valencia para Home Assistant",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_briefing(include_debug: bool = False) -> dict:
    """
    Devuelve el briefing: desde caché si es válida, regenerado si no.
    """
    cached = cache_store.load()
    if cached is not None:
        logger.info("Respondiendo desde caché")
        if include_debug:
            # La caché no guarda debug para no inflar el archivo;
            # en /debug regeneramos siempre para tener stats frescas.
            pass
        else:
            return cached

    logger.info("Caché vacía o expirada — ejecutando pipeline...")
    result = pipeline.run()
    briefing_dict = result.to_dict(include_debug=False)
    briefing_dict["cached"] = False
    cache_store.save(briefing_dict)

    if include_debug:
        return result.to_dict(include_debug=True)

    return briefing_dict


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Health check — confirma que el add-on está vivo y muestra config activa."""
    return {
        "status": "ok",
        "service": "valencia-briefing-api",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "max_items": MAX_ITEMS,
            "max_age_hours": MAX_AGE_HOURS,
            "cache_ttl_minutes": CACHE_TTL_MINUTES,
        },
    }


@app.get("/valencia_briefing")
def valencia_briefing():
    """
    Devuelve el briefing completo (noticias + eventos).
    Usa caché persistente en /data/briefing_cache.json.
    El campo 'cached: true' indica si la respuesta viene de caché.
    """
    try:
        data = _build_briefing(include_debug=False)
        return JSONResponse(content=data)
    except Exception as exc:
        logger.exception("Error generando briefing")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/refresh")
def refresh():
    """
    Invalida la caché y regenera el briefing inmediatamente.
    Útil para llamar desde una automatización de HA cuando quieras
    datos frescos antes de que expire el TTL normal.
    """
    try:
        cache_store.invalidate()
        data = _build_briefing(include_debug=False)
        data["refreshed"] = True
        return JSONResponse(content=data)
    except Exception as exc:
        logger.exception("Error en /refresh")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/debug")
def debug():
    """
    Igual que /valencia_briefing pero incluye estadísticas por fuente:
    cuántas entradas se leyeron, cuántas pasaron el filtro, si hubo errores.
    Siempre regenera (no usa caché) para mostrar stats reales.
    """
    try:
        cache_store.invalidate()
        data = _build_briefing(include_debug=True)
        return JSONResponse(content=data)
    except Exception as exc:
        logger.exception("Error en /debug")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
