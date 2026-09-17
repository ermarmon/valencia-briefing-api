"""
Persistencia del historial de briefings generados.

El historial se almacena separado de la caché de noticias: la primera cambia
con cada consulta a los feeds; el segundo solo se actualiza cuando Home
Assistant ha generado y enviado un briefing de voz correctamente.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .settings import BRIEFING_HISTORY_LIMIT, HISTORY_FILE_PATH

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_all() -> list[dict]:
    """Lee y valida las entradas guardadas, de la más antigua a la más nueva."""
    if not HISTORY_FILE_PATH.exists():
        return []

    try:
        payload = json.loads(HISTORY_FILE_PATH.read_text(encoding="utf-8"))
        entries = payload.get("items", []) if isinstance(payload, dict) else []
        if not isinstance(entries, list):
            raise ValueError("items no es una lista")

        valid_entries = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text = entry.get("text")
            created_at = entry.get("created_at")
            if not isinstance(text, str) or not text.strip() or not isinstance(created_at, str):
                continue
            valid_entries.append(
                {
                    "text": text.strip(),
                    "created_at": created_at,
                    "briefing_id": entry.get("briefing_id"),
                }
            )
        return valid_entries
    except Exception as exc:
        logger.warning("No se pudo leer el historial de briefings: %s", exc)
        return []


def _save_all(entries: list[dict]) -> None:
    """Guarda de forma atómica para no dejar un JSON parcial ante un reinicio."""
    HISTORY_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(f"{HISTORY_FILE_PATH}.tmp")
    payload = {"version": 1, "items": entries}
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(HISTORY_FILE_PATH)


def list_entries(limit: int) -> list[dict]:
    """Devuelve los últimos registros, del más reciente al más antiguo."""
    safe_limit = max(1, min(limit, BRIEFING_HISTORY_LIMIT))
    return list(reversed(_load_all()[-safe_limit:]))


def record(text: str, briefing_id: str | None = None) -> tuple[dict, bool]:
    """
    Añade un briefing y conserva solo los últimos registros configurados.

    Si se repite un briefing_id o el mismo texto consecutivo, se devuelve la
    entrada existente sin crear un duplicado. Esto hace seguro reintentar el
    POST desde Home Assistant.
    """
    normalized_text = text.strip()
    normalized_id = briefing_id.strip() if briefing_id else None
    entries = _load_all()

    if normalized_id:
        for entry in reversed(entries):
            if entry.get("briefing_id") == normalized_id:
                return entry, False
    elif entries and entries[-1]["text"] == normalized_text:
        return entries[-1], False

    entry = {
        "text": normalized_text,
        "created_at": _now_iso(),
        "briefing_id": normalized_id,
    }
    entries.append(entry)
    _save_all(entries[-BRIEFING_HISTORY_LIMIT:])
    return entry, True