"""
feed_loader.py — Carga y valida el archivo feeds.yaml.

Orden de búsqueda:
  1. /data/feeds.yaml  (editable por el usuario, persiste entre reinicios)
  2. /app/src/feeds_default.yaml  (empaquetado en la imagen, solo lectura)

Si ninguno existe (desarrollo local) devuelve una lista vacía y loguea warning.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .models import FeedSource
from .settings import FEEDS_YAML_PATH, FEEDS_DEFAULT_PATH

logger = logging.getLogger(__name__)


def _load_yaml(path: Path) -> dict:
    try:
        content = path.read_text(encoding="utf-8")
        return yaml.safe_load(content) or {}
    except FileNotFoundError:
        return {}
    except yaml.YAMLError as exc:
        logger.error("Error parseando %s: %s", path, exc)
        return {}


def load_feeds() -> tuple[list[FeedSource], dict]:
    """
    Carga fuentes y keywords desde feeds.yaml.

    Returns:
        (sources, keywords_dict)
        sources: lista de FeedSource habilitadas
        keywords_dict: {"valencia": [...], "boost": [...]}
    """
    # Intentar ruta editable primero
    data = _load_yaml(FEEDS_YAML_PATH)
    if data:
        logger.info("feeds.yaml cargado desde %s", FEEDS_YAML_PATH)
    else:
        data = _load_yaml(FEEDS_DEFAULT_PATH)
        if data:
            logger.info("feeds.yaml cargado desde imagen por defecto (%s)", FEEDS_DEFAULT_PATH)
        else:
            logger.warning("No se encontró feeds.yaml en ninguna ruta — sin fuentes configuradas")
            return [], {}

    # Parsear fuentes
    sources: list[FeedSource] = []
    for raw in data.get("sources", []):
        try:
            src = FeedSource(
                name=raw["name"],
                url=raw["url"],
                type=raw.get("type", "news"),
                enabled=raw.get("enabled", True),
                priority=int(raw.get("priority", 2)),
            )
            if src.enabled:
                sources.append(src)
        except (KeyError, TypeError) as exc:
            logger.warning("Fuente malformada en feeds.yaml, ignorando: %s — %s", raw, exc)

    keywords: dict = data.get("keywords", {})
    logger.info("Fuentes habilitadas: %d | Keywords Valencia: %d | Boost: %d",
                len(sources),
                len(keywords.get("valencia", [])),
                len(keywords.get("boost", [])))

    return sources, keywords
