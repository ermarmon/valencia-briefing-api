"""
scorer.py — Scoring y priorización de entradas.

Cada entrada recibe una puntuación float (mayor = más relevante).
Los factores son aditivos y configurados como constantes en este módulo
para facilitar ajustes futuros.

Factores aplicados:
  RECENCY      → entradas más recientes puntúan más (decaimiento lineal)
  VALENCIA_KW  → menciona términos de Valencia en título/resumen
  BOOST_KW     → menciona términos de boost (fallas, mercado, etc.)
  SOURCE_PRIO  → fuentes de prioridad 1 puntúan más que prioridad 3
  EVENT_TODAY  → eventos de hoy o mañana reciben bonus extra
"""

from __future__ import annotations

import logging
import unicodedata
from datetime import datetime, timedelta, timezone

from .models import BriefingEntry, FeedSource

logger = logging.getLogger(__name__)

# ── Pesos de scoring (ajustables sin tocar lógica) ───────────────────────────
W_RECENCY_MAX = 3.0      # puntos máximos por recencia (entrada de ahora mismo)
W_RECENCY_DECAY_H = 24   # en cuántas horas la puntuación de recencia llega a 0
W_VALENCIA_KW = 2.0      # por cada keyword de Valencia encontrada (máx 3 aplicaciones)
W_BOOST_KW = 1.0         # por cada keyword de boost encontrada (máx 3 aplicaciones)
W_SOURCE_P1 = 1.5        # bonus si fuente priority=1
W_SOURCE_P2 = 0.5        # bonus si fuente priority=2
W_EVENT_TODAY = 3.0      # bonus si evento es hoy
W_EVENT_TOMORROW = 1.5   # bonus si evento es mañana


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return nfkd.encode("ascii", "ignore").decode("ascii")


def _recency_score(date: datetime) -> float:
    """Puntuación lineal decreciente según antigüedad."""
    now = datetime.now(timezone.utc)
    age_hours = max(0.0, (now - date).total_seconds() / 3600)
    if age_hours >= W_RECENCY_DECAY_H:
        return 0.0
    return W_RECENCY_MAX * (1.0 - age_hours / W_RECENCY_DECAY_H)


def _keyword_score(entry: BriefingEntry, keywords: dict) -> float:
    """Suma puntos por keywords de Valencia y boost encontradas."""
    blob = _normalize(f"{entry.title} {entry.summary}")
    score = 0.0

    valencia_terms = [_normalize(k) for k in keywords.get("valencia", [])]
    hits_v = sum(1 for t in valencia_terms if t in blob)
    score += min(hits_v, 3) * W_VALENCIA_KW

    boost_terms = [_normalize(k) for k in keywords.get("boost", [])]
    hits_b = sum(1 for t in boost_terms if t in blob)
    score += min(hits_b, 3) * W_BOOST_KW

    return score


def _source_score(entry: BriefingEntry, sources: list[FeedSource]) -> float:
    """Bonus basado en la prioridad configurada de la fuente."""
    for src in sources:
        if src.name == entry.source:
            if src.priority == 1:
                return W_SOURCE_P1
            if src.priority == 2:
                return W_SOURCE_P2
    return 0.0


def _event_timeliness_score(entry: BriefingEntry) -> float:
    """Bonus para eventos de hoy o mañana (solo aplica a category='event')."""
    if entry.category != "event":
        return 0.0
    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    entry_date = entry.date.date()
    if entry_date == today:
        return W_EVENT_TODAY
    if entry_date == tomorrow:
        return W_EVENT_TOMORROW
    return 0.0


def score_and_sort(
    entries: list[BriefingEntry],
    keywords: dict,
    sources: list[FeedSource],
) -> list[BriefingEntry]:
    """
    Calcula el score de cada entrada y devuelve la lista ordenada
    de mayor a menor relevancia.
    """
    for entry in entries:
        entry.score = (
            _recency_score(entry.date)
            + _keyword_score(entry, keywords)
            + _source_score(entry, sources)
            + _event_timeliness_score(entry)
        )

    sorted_entries = sorted(entries, key=lambda e: e.score, reverse=True)
    logger.debug(
        "Top 3 scores: %s",
        [(e.title[:40], round(e.score, 2)) for e in sorted_entries[:3]],
    )
    return sorted_entries
