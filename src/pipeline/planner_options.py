"""
src/pipeline/planner_options.py

Loads preset weights and wizard options from planner_config.json.
"""

import os
import json
from typing import Dict, List, Tuple, Any

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "planner_config.json")


def _load_planner_config() -> Dict[str, Any]:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_CONFIG = _load_planner_config()

DEFAULT_PRESET_WEIGHTS: Dict[str, Dict[str, float]] = _CONFIG.get("preset_weights", {})
TAXONOMY_OPTIONS: List[Tuple[str, str]] = [tuple(opt) for opt in _CONFIG.get("taxonomy_options", [])]
HARDWARE_OPTIONS: List[Tuple[str, str]] = [tuple(opt) for opt in _CONFIG.get("hardware_options", [])]
TARGET_OPTIONS: List[Tuple[str, str]] = [tuple(opt) for opt in _CONFIG.get("target_options", [])]
SECURITY_OPTIONS: List[Tuple[str, str]] = [tuple(opt) for opt in _CONFIG.get("security_options", [])]
