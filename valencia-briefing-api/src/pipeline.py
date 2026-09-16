"""
pipeline.py — Orquestador de la pipeline completa del briefing.

Fases en orden:
  1. Cargar fuentes y keywords desde feeds.yaml
  2. Descargar todos los feeds (en paralelo con ThreadPoolExecutor)
  3. Filtrar por keywords de Valencia
  4. Deduplicar
  5. Scoring y ordenación
  6. Separar en news / events y aplicar límite de items
  7. Construir BriefingResult

La paralelización en paso 2 usa threads (no async) porque feedparser
es síncrono y bloquea. Para 4-6 fuentes el overhead es mínimo.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from .feed_loader import load_feeds
from .fetcher import fetch_source
from .filter_dedup import deduplicate, filter_by_keywords
from .models import BriefingEntry, BriefingResult, SourceStats
from .scorer import score_and_sort
from .settings import MAX_ITEMS

logger = logging.getLogger(__name__)

# Máximo de threads simultáneos para descargar feeds
_MAX_WORKERS = 6


def run() -> BriefingResult:
    """
    Ejecuta la pipeline completa y devuelve un BriefingResult.
    Nunca lanza excepción: errores por fuente quedan en SourceStats.error.
    """
    logger.info("═══ Iniciando pipeline del briefing ═══")
    started_at = datetime.now(timezone.utc)

    # ── 1. Cargar configuración ───────────────────────────────────────────────
    sources, keywords = load_feeds()
    if not sources:
        logger.warning("Sin fuentes configuradas — briefing vacío")
        return BriefingResult(generated_at=started_at)

    # ── 2. Descargar feeds en paralelo ────────────────────────────────────────
    all_entries: list[BriefingEntry] = []
    all_stats: list[SourceStats] = []

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        future_to_source = {
            executor.submit(fetch_source, src): src for src in sources
        }
        for future in as_completed(future_to_source):
            entries, stats = future.result()
            all_entries.extend(entries)
            all_stats.append(stats)

    logger.info("Total entradas brutas: %d de %d fuentes", len(all_entries), len(sources))

    # ── 3. Filtrar por keywords de Valencia ───────────────────────────────────
    filtered = filter_by_keywords(all_entries, keywords)

    # ── 4. Deduplicar ─────────────────────────────────────────────────────────
    unique = deduplicate(filtered)

    # ── 5. Scoring y ordenación ───────────────────────────────────────────────
    scored = score_and_sort(unique, keywords, sources)

    # ── 6. Separar en news / events y aplicar límite ─────────────────────────
    news = [e for e in scored if e.category == "news"][:MAX_ITEMS]
    events = [e for e in scored if e.category == "event"][:MAX_ITEMS]

    logger.info(
        "Pipeline completada en %.2fs → %d noticias, %d eventos",
        (datetime.now(timezone.utc) - started_at).total_seconds(),
        len(news),
        len(events),
    )

    return BriefingResult(
        generated_at=started_at,
        news=news,
        events=events,
        source_stats=all_stats,
    )
