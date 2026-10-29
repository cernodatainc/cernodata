"""
src/quality/layers.py

Document verification layers and criteria definitions.
Provides layer enumeration, aliases normalization, and criteria descriptions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


class VerificationLayer(str, Enum):
    """Normalized identifiers for document verification quality layers."""
    SYMBOLS = "symbols"
    DIACRITICS = "diacritics"
    STRUCTURE = "structure"
    TABLES = "tables"
    GEOMETRY = "geometry"

    def __str__(self) -> str:
        return str(self.value)


LAYER_ALIASES: Dict[str, str] = {
    "symbol": VerificationLayer.SYMBOLS.value,
    "symbols": VerificationLayer.SYMBOLS.value,
    "garbage": VerificationLayer.SYMBOLS.value,
    "ocr_noise": VerificationLayer.SYMBOLS.value,
    "diacritic": VerificationLayer.DIACRITICS.value,
    "diacritics": VerificationLayer.DIACRITICS.value,
    "language": VerificationLayer.DIACRITICS.value,
    "lang": VerificationLayer.DIACRITICS.value,
    "structure": VerificationLayer.STRUCTURE.value,
    "structural": VerificationLayer.STRUCTURE.value,
    "hierarchy": VerificationLayer.STRUCTURE.value,
    "layout": VerificationLayer.STRUCTURE.value,
    "table": VerificationLayer.TABLES.value,
    "tables": VerificationLayer.TABLES.value,
    "grid": VerificationLayer.TABLES.value,
    "table_grid": VerificationLayer.TABLES.value,
    "geometry": VerificationLayer.GEOMETRY.value,
    "spatial": VerificationLayer.GEOMETRY.value,
    "collision": VerificationLayer.GEOMETRY.value,
    "bounding_box": VerificationLayer.GEOMETRY.value,
    "bbox": VerificationLayer.GEOMETRY.value,
}

ALL_VERIFICATION_LAYERS: List[str] = [
    VerificationLayer.SYMBOLS.value,
    VerificationLayer.DIACRITICS.value,
    VerificationLayer.STRUCTURE.value,
    VerificationLayer.TABLES.value,
    VerificationLayer.GEOMETRY.value,
]

DEFAULT_VERIFICATION_LAYERS: List[str] = [
    VerificationLayer.SYMBOLS.value,
    VerificationLayer.DIACRITICS.value,
    VerificationLayer.STRUCTURE.value,
    VerificationLayer.TABLES.value,
    VerificationLayer.GEOMETRY.value,
]

LAYER_METADATA: Dict[str, Dict[str, Any]] = {
    VerificationLayer.SYMBOLS.value: {
        "level": 1,
        "name": "Symbols & Character Integrity",
        "description": "OCR noise, character corruption, punctuation soup, and alphanumeric density.",
    },
    VerificationLayer.DIACRITICS.value: {
        "level": 2,
        "name": "Language & Diacritic Accuracy",
        "description": "Language-specific diacritic anomalies, foreign diacritic conflicts, and OCR substitution.",
    },
    VerificationLayer.STRUCTURE.value: {
        "level": 3,
        "name": "Structural & Semantic Hierarchy",
        "description": "Heading hierarchy, orphan headings, empty structural containers, and ordering invariants.",
    },
    VerificationLayer.TABLES.value: {
        "level": 4,
        "name": "Table Grid & Cell Alignment",
        "description": "Table grid consistency, row-column alignment, and tabular cell boundaries.",
    },
    VerificationLayer.GEOMETRY.value: {
        "level": 5,
        "name": "Spatial Geometry & Decollision",
        "description": "Bounding box validity, coordinate inversion, zero-area nodes, and spatial overlaps.",
    },
}


def normalize_layer_name(name: str) -> Optional[str]:
    """Resolves a raw layer name or alias to canonical VerificationLayer value."""
    if not name:
        return None
    cleaned = name.strip().lower()
    return LAYER_ALIASES.get(cleaned, cleaned)


def normalize_layers(layers: Optional[Sequence[str]]) -> List[str]:
    """
    Normalizes a sequence of layer names into an ordered list of unique canonical layers.
    If input is None, returns a copy of ALL_VERIFICATION_LAYERS.
    """
    if layers is None:
        return list(ALL_VERIFICATION_LAYERS)

    normalized: List[str] = []
    seen = set()
    for raw in layers:
        resolved = normalize_layer_name(raw)
        if resolved and resolved not in seen:
            seen.add(resolved)
            normalized.append(resolved)

    return normalized
