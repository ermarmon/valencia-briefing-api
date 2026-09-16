"""
fetcher.py — Descarga y parseo de feeds RSS/Atom.

Convierte cada entrada de feedparser a BriefingEntry normalizado.
Un feed caído o malformado no tumba la pipeline: se registra en SourceStats
y se continúa con el resto de fuentes.

NOTA: feedparser.parse(url) usa urllib internamente sin User-Agent, lo que
provoca que muchos servidores devuelvan HTML (403/captcha) en lugar de XML.
Solución: descargar el contenido manualmente con httpx enviando un
User-Agent de navegador real, y luego pasar el XML crudo a feedparser.parse().
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone

import feedparser
import httpx
from dateutil import parser as dateparser

from .models import BriefingEntry, FeedSource, SourceStats
from .settings import MAX_AGE_HOURS

logger = logging.getLogger(__name__)

# User-Agent que imita un navegador real — suficiente para la mayoría de feeds
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_HTTP_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}

_HTTP_TIMEOUT = 15.0


def _cutoff() -> datetime:
    from datetime import timedelta
    return datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)


def _clean_html(text: str) -> str:
    """Elimina etiquetas HTML básicas de un string."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _fetch_raw(url: str) -> bytes:
    """
    Descarga el contenido de la URL con httpx y headers de navegador.
    Devuelve los bytes crudos para pasarlos a feedparser.
    Lanza excepción si falla la descarga.
    """
    with httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        response = client.get(url, headers=_HTTP_HEADERS)
        response.raise_for_status()
        return response.content


def _parse_date(entry: feedparser.FeedParserDict) -> datetime:
    """
    Extrae la fecha de una entrada feedparser.
    Prioridad: published_parsed > updated_parsed > campo published en texto.
    Devuelve siempre un datetime aware (UTC).
    """
    for attr in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, attr, None)
        if struct:
            try:
                import calendar
                ts = calendar.timegm(struct)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                pass

    for attr in ("published", "updated"):
        raw = getattr(entry, attr, "") or ""
        if raw:
            try:
                dt = dateparser.parse(raw)
                if dt:
                    return dt.astimezone(timezone.utc)
            except Exception:
                pass

    logger.debug("Entrada sin fecha detectada, usando now(): %s", getattr(entry, "title", "?"))
    return datetime.now(timezone.utc)


def _dedup_key(url: str, title: str) -> str:
    base = url.strip() if url.strip() else title.lower().strip()
    return hashlib.md5(base.encode()).hexdigest()[:16]


def _entry_to_briefing(
    entry: feedparser.FeedParserDict,
    source: FeedSource,
) -> BriefingEntry | None:
    title = _clean_html(getattr(entry, "title", "") or "")
    if not title:
        return None

    url = getattr(entry, "link", "") or ""
    summary_raw = (
        getattr(entry, "summary", "")
        or getattr(entry, "description", "")
        or ""
    )
    summary = _clean_html(summary_raw)
    if len(summary) > 350:
        summary = summary[:347] + "…"

    date = _parse_date(entry)

    if date < _cutoff():
        return None

    return BriefingEntry(
        title=title,
        source=source.name,
        date=date,
        url=url,
        summary=summary,
        category=source.type,
        dedup_key=_dedup_key(url, title),
    )


def fetch_source(source: FeedSource) -> tuple[list[BriefingEntry], SourceStats]:
    """
    Lee un feed y devuelve sus entradas normalizadas + estadísticas.
    Nunca lanza excepción: errores se capturan en SourceStats.error.
    """
    stats = SourceStats(name=source.name, url=source.url, type=source.type)
    entries: list[BriefingEntry] = []

    try:
        logger.info("Descargando feed: %s (%s)", source.name, source.url)

        # Descarga manual con User-Agent de navegador para evitar bloqueos
        raw_content = _fetch_raw(source.url)
        logger.debug("%s → %d bytes descargados", source.name, len(raw_content))

        # Parsear desde bytes (feedparser acepta bytes directamente)
        feed = feedparser.parse(raw_content)

        if feed.bozo and not feed.entries:
            raise ValueError(f"Feed inválido tras descarga: {feed.bozo_exception}")

        if feed.bozo:
            # bozo pero con entradas: parseo parcial, continuar con aviso
            logger.warning("%s: feed con advertencias XML (bozo), continuando con %d entradas",
                source.name, len(feed.entries))

        stats.fetched = len(feed.entries)

        for raw_entry in feed.entries:
            parsed = _entry_to_briefing(raw_entry, source)
            if parsed is not None:
                entries.append(parsed)

        stats.after_filter = len(entries)
        logger.info("%s → %d leídas, %d tras filtro de antigüedad",
                    source.name, stats.fetched, stats.after_filter)

    except Exception as exc:
        stats.error = str(exc)
        logger.error("Error en fuente '%s': %s", source.name, exc)

    return entries, stats

