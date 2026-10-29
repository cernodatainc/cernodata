"""
src/quality/registry.py

Modular verification layer registry and extensible quality evaluation handlers.
Allows defining and registering verification layers independently without modifying
central violation detection and scoring algorithms.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from src.quality.handlers import (
    DiacriticsLayerHandler,
    GeometryLayerHandler,
    StructureLayerHandler,
    SymbolsLayerHandler,
    TablesLayerHandler,
    VerificationLayerHandler,
)
from src.quality.layers import normalize_layer_name, normalize_layers


class QualityRegistry:
    """Registry maintaining active verification layer handlers and criteria lookup."""

    def __init__(self) -> None:
        self._handlers: Dict[str, VerificationLayerHandler] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Initializes built-in verification layer handlers."""
        for handler in (
            SymbolsLayerHandler(),
            DiacriticsLayerHandler(),
            StructureLayerHandler(),
            TablesLayerHandler(),
            GeometryLayerHandler(),
        ):
            self.register(handler)

    def register(self, handler: VerificationLayerHandler) -> None:
        """Registers a quality verification layer handler."""
        self._handlers[handler.layer_id] = handler

    def get(self, name: str) -> Optional[VerificationLayerHandler]:
        """Looks up a registered verification layer handler by name or alias."""
        norm = normalize_layer_name(name)
        return self._handlers.get(norm or name)

    def get_all(self) -> List[VerificationLayerHandler]:
        """Returns all registered verification layer handlers ordered by level."""
        return sorted(self._handlers.values(), key=lambda h: h.level)

    def get_active(self, layers: Optional[Sequence[str]] = None) -> List[VerificationLayerHandler]:
        """Returns registered handlers matching requested layers sequence or all if None."""
        if layers is None:
            return self.get_all()
        active_ids = set(normalize_layers(layers))
        return [h for h in self.get_all() if h.layer_id in active_ids]


default_quality_registry = QualityRegistry()

__all__ = [
    "DiacriticsLayerHandler",
    "GeometryLayerHandler",
    "QualityRegistry",
    "StructureLayerHandler",
    "SymbolsLayerHandler",
    "TablesLayerHandler",
    "VerificationLayerHandler",
    "default_quality_registry",
]
