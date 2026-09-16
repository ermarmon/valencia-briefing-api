"""
settings.py — Configuración central del add-on.

Lee /data/options.json inyectado por el Supervisor de HA OS y expone
todas las constantes de rutas y opciones en un único lugar.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Rutas del sistema ────────────────────────────────────────────────────────
# En HA OS el Supervisor mapea /data y /config al contenedor.
# En desarrollo local estas rutas no existen → usamos /tmp como fallback.
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/config"))

FEEDS_YAML_PATH = DATA_DIR / "feeds.yaml"
FEEDS_DEFAULT_PATH = Path("/app/src/feeds_default.yaml")
CACHE_FILE_PATH = DATA_DIR / "briefing_cache.json"
OPTIONS_FILE_PATH = DATA_DIR / "options.json"

# ── Defaults de opciones ─────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "max_items": 20,
    "max_age_hours": 48,
    "cache_ttl_minutes": 60,
    "log_level": "info",
}


def _load_options() -> dict:
    if OPTIONS_FILE_PATH.exists():
        try:
            opts = json.loads(OPTIONS_FILE_PATH.read_text())
            logger.info("Opciones cargadas desde %s", OPTIONS_FILE_PATH)
            return {**_DEFAULTS, **opts}
        except Exception as exc:
            logger.warning("No se pudo leer options.json: %s — usando defaults", exc)
    return _DEFAULTS.copy()


OPTIONS: dict = _load_options()

# Accesos directos tipados
MAX_ITEMS: int = int(OPTIONS["max_items"])
MAX_AGE_HOURS: int = int(OPTIONS["max_age_hours"])
CACHE_TTL_MINUTES: int = int(OPTIONS["cache_ttl_minutes"])
LOG_LEVEL: str = OPTIONS["log_level"].upper()
