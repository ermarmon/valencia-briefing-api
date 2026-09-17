"""
app.py — Valencia Briefing API v2.1.1

Endpoints:
  GET  /                    → healthcheck con versión y opciones activas
  GET  /valencia_briefing   → briefing completo (con caché persistente)
  GET  /refresh             → fuerza regeneración invalidando caché
  GET  /debug               → igual que /valencia_briefing pero con info de fuentes
  GET  /briefing_history    → últimos briefings generados
  POST /briefing_history    → registra el briefing enviado por Home Assistant
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import cache_store, history_store, pipeline
from .settings import (
    BRIEFING_HISTORY_LIMIT,
    CACHE_TTL_MINUTES,
    LOG_LEVEL,
    MAX_AGE_HOURS,
    MAX_ITEMS,
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Valencia Briefing API",
    version="2.1.1",
    description="Agregador local de noticias y eventos de Valencia para Home Assistant",
)


class BriefingHistoryInput(BaseModel):
    """Mensaje final del briefing, una vez enviado por Home Assistant."""

    text: str = Field(min_length=1, max_length=12000)
    briefing_id: str | None = Field(default=None, max_length=100)


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
        "version": "2.1.1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "max_items": MAX_ITEMS,
            "max_age_hours": MAX_AGE_HOURS,
            "cache_ttl_minutes": CACHE_TTL_MINUTES,
            "briefing_history_limit": BRIEFING_HISTORY_LIMIT,
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


@app.get("/briefing_history")
def briefing_history(
    limit: int = Query(default=BRIEFING_HISTORY_LIMIT, ge=1, le=10),
):
    """
    Devuelve los últimos briefings completos, del más reciente al más antiguo.

    La automatización puede usar estos textos como contexto para pedir una
    redacción distinta al modelo de IA.
    """
    try:
        entries = history_store.list_entries(limit)
        return {
            "items": entries,
            "count": len(entries),
            "retention_limit": BRIEFING_HISTORY_LIMIT,
        }
    except Exception as exc:
        logger.exception("Error leyendo el historial de briefings")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/briefing_history")
def save_briefing_history(payload: BriefingHistoryInput):
    """
    Registra el texto final que Home Assistant ha enviado por TTS.

    briefing_id es opcional, pero se recomienda usar la fecha local
    (por ejemplo, 2026-09-17) para hacer la operación idempotente.
    """
    try:
        entry, created = history_store.record(
            text=payload.text,
            briefing_id=payload.briefing_id,
        )
        # Home Assistant's rest_command only needs acknowledgement.
        # avoids keeping a response body open on the Supervisor network.
        return Response(status_code=204)
    except Exception as exc:
        logger.exception("Error guardando el historial de briefings")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
