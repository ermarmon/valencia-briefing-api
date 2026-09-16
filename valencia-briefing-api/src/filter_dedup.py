"""
filter_dedup.py — Filtrado por relevancia y deduplicación.

Dos pasos independientes aplicados en secuencia por la pipeline:
  1. filter_by_keywords: descarta entradas sin ninguna mención a Valencia
     o términos relacionados configurados en feeds.yaml.
  2. deduplicate: elimina duplicados por URL exacta o título muy similar.
"""

from __future__ import annotations

import logging
import unicodedata

from .models import BriefingEntry

logger = logging.getLogger(__name__)


# ── Utilidades de texto ───────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """
    Normaliza un texto para comparaciones:
    - minúsculas
    - elimina acentos
    - colapsa espacios
    """
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_str.split())


def _text_blob(entry: BriefingEntry) -> str:
    """Concatena título + resumen para búsqueda de keywords."""
    return _normalize(f"{entry.title} {entry.summary}")


# ── Filtrado ──────────────────────────────────────────────────────────────────

def filter_by_keywords(
    entries: list[BriefingEntry],
    keywords: dict,
) -> list[BriefingEntry]:
    """
    Mantiene solo las entradas que mencionan al menos un término
    de la lista keywords["valencia"].

    Si la lista está vacía (feeds.yaml sin sección keywords), deja pasar todo.
    """
    valencia_terms = [_normalize(k) for k in keywords.get("valencia", [])]

    if not valencia_terms:
        logger.debug("Sin keywords de Valencia definidos — sin filtrado por relevancia")
        return entries

    kept: list[BriefingEntry] = []
    dropped = 0

    for entry in entries:
        blob = _text_blob(entry)
        if any(term in blob for term in valencia_terms):
            kept.append(entry)
        else:
            dropped += 1
            logger.debug("Descartada (sin keywords Valencia): %s", entry.title[:60])

    logger.info("Filtro keywords: %d mantenidas, %d descartadas", len(kept), dropped)
    return kept


# ── Deduplicación ─────────────────────────────────────────────────────────────

def deduplicate(entries: list[BriefingEntry]) -> list[BriefingEntry]:
    """
    Elimina duplicados en dos pasadas:
        1. Por dedup_key (URL o hash de URL) — duplicados exactos.
        2. Por título normalizado — misma noticia de distinta fuente.

    Cuando hay duplicado, se queda la entrada con menor priority de fuente
    (prioridad numérica más baja = mejor fuente). Como el scoring aún no
    se ha aplicado, usamos orden de inserción como criterio secundario:
    la primera que llega gana.
    """
    seen_keys: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[BriefingEntry] = []
    dropped = 0

    for entry in entries:
        # Pasada 1: dedup por clave de URL
        if entry.dedup_key and entry.dedup_key in seen_keys:
            dropped += 1
            logger.debug("Dedup (URL): %s", entry.title[:60])
            continue

        # Pasada 2: dedup por título normalizado (primeros 80 chars)
        title_key = _normalize(entry.title)[:80]
        if title_key in seen_titles:
            dropped += 1
            logger.debug("Dedup (título): %s", entry.title[:60])
            continue

        if entry.dedup_key:
            seen_keys.add(entry.dedup_key)
        seen_titles.add(title_key)
        unique.append(entry)

    logger.info("Deduplicación: %d únicas, %d eliminadas", len(unique), dropped)
    return unique
