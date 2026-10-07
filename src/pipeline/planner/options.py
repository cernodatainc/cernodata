"""
src/pipeline/planner/options.py

Loads preset weights and wizard options from planner_config.json.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Tuple

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "planner_config.json")


def _load_planner_config() -> Dict[str, Any]:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_CONFIG = _load_planner_config()

DEFAULT_PRESET_WEIGHTS: Dict[str, Dict[str, float]] = _CONFIG.get("preset_weights", {})
TAXONOMY_OPTIONS: List[Tuple[str, str]] = [tuple(opt) for opt in _CONFIG.get("taxonomy_options", [])]
TARGET_OPTIONS: List[Tuple[str, str]] = [tuple(opt) for opt in _CONFIG.get("target_options", [])]
SECURITY_OPTIONS: List[Tuple[str, str]] = [tuple(opt) for opt in _CONFIG.get("security_options", [])]


@dataclass(frozen=True)
class WizardDimension:
    """Strongly-typed definition of a questionnaire decision dimension."""
    key: str
    title: str
    description: str
    options: List[Tuple[str, str]]
    default: str

    def to_dict(self) -> Dict[str, Any]:
        """Serializes dimension attributes to standard dictionary."""
        return asdict(self)


WIZARD_DIMENSIONS: List[WizardDimension] = [
    WizardDimension(
        key="taxonomy",
        title="Document Taxonomy",
        description="Select the primary structural layout shape",
        options=TAXONOMY_OPTIONS,
        default="general_text",
    ),
    WizardDimension(
        key="target",
        title="Quality vs. Speed Target",
        description="Throughput priority versus bounding box layout fidelity",
        options=TARGET_OPTIONS,
        default="high_precision_structure",
    ),
    WizardDimension(
        key="security",
        title="Security / Network Constraint",
        description="External cloud API allowance vs. air-gapped local model",
        options=SECURITY_OPTIONS,
        default="air_gapped_local",
    ),
]
