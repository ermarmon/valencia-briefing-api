"""
models.py — Estructuras de datos del dominio.

Usar dataclasses con tipos explícitos hace que el código sea
más fácil de mantener y refactorizar que trabajar con dicts en bruto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FeedSource:
    """Representa una fuente RSS/Atom definida en feeds.yaml."""
    name: str
    url: str
    type: str           # "news" | "event"
    enabled: bool = True
    priority: int = 2   # 1=alta, 2=media, 3=baja


@dataclass
class BriefingEntry:
    """
    Entrada normalizada del briefing, independiente de la fuente.
    Todos los campos de texto son strings; date es siempre datetime con tz.
    """
    title: str
    source: str
    date: datetime
    url: str
    summary: str
    category: str       # "news" | "event"
    score: float = 0.0  # calculado por el scorer

    # Clave de deduplicación: se calcula a partir de url o título normalizado
    dedup_key: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "source": self.source,
            "date": self.date.isoformat(),
            "url": self.url,
            "summary": self.summary,
            "category": self.category,
        }


@dataclass
class SourceStats:
    """Estadísticas de una fuente, expuestas en /debug."""
    name: str
    url: str
    type: str
    fetched: int = 0        # entradas leídas del feed
    after_filter: int = 0   # tras filtrar por keywords y antigüedad
    error: str = ""         # vacío si ok


@dataclass
class BriefingResult:
    """Resultado completo devuelto por la pipeline."""
    generated_at: datetime
    news: list[BriefingEntry] = field(default_factory=list)
    events: list[BriefingEntry] = field(default_factory=list)
    source_stats: list[SourceStats] = field(default_factory=list)

    @property
    def count(self) -> dict:
        return {"news": len(self.news), "events": len(self.events)}

    def to_dict(self, include_debug: bool = False) -> dict:
        out: dict = {
            "generated_at": self.generated_at.isoformat(),
            "count": self.count,
            "news": [e.to_dict() for e in self.news],
            "events": [e.to_dict() for e in self.events],
            "sources": [s.name for s in self.source_stats if not s.error],
        }
        if include_debug:
            out["debug"] = [
                {
                    "source": s.name,
                    "url": s.url,
                    "type": s.type,
                    "fetched": s.fetched,
                    "after_filter": s.after_filter,
                    "error": s.error or None,
                }
                for s in self.source_stats
            ]
        return out
