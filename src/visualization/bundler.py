"""
src/visualization/bundler.py

On-the-fly JavaScript bundle builder for cernodata web visualization interfaces.
Concatenates modular concern scripts at runtime without persisting bundled assets on disk.
"""

from __future__ import annotations

import os
from typing import List, Optional, Sequence

_VIS_DIR: str = os.path.dirname(os.path.abspath(__file__))

LANDING_MODULE_ORDER: List[str] = [
    "utils.js",
    "navigation.js",
    "execution.js",
    "runs.js",
    "results.js",
    "matrix_grid.js",
    "hints.js",
    "explorer.js",
    "app.js",
]

DATA_SHAPE_MODULE_ORDER: List[str] = [
    "constants.js",
    "scoring.js",
    "ui.js",
    "runs.js",
    "submission.js",
    "app.js",
]


def bundle_js_modules(
    directory: str, module_order: Sequence[str], header_title: Optional[str] = None
) -> str:
    """Concatenates modular JavaScript source files from a directory in dependency order."""
    parts: List[str] = []
    if header_title:
        parts.append(
            "/* ==========================================================================\n"
            f" * {header_title}\n"
            " * ========================================================================== */\n"
        )
    for mod_name in module_order:
        mod_path = os.path.join(directory, mod_name)
        if os.path.exists(mod_path):
            with open(mod_path, "r", encoding="utf-8") as f:
                parts.append(f"/* === Concern Module: {mod_name} === */\n" + f.read())
    return "\n\n".join(parts)


def bundle_landing_js() -> str:
    """Concatenates modular landing page JavaScript sources on the fly in dependency order."""
    return bundle_js_modules(
        os.path.join(_VIS_DIR, "landing"),
        LANDING_MODULE_ORDER,
        "cernodata Ingestion Hub Dashboard Runtime (Built On The Fly)",
    )


def get_landing_js() -> str:
    """Retrieves dynamically assembled landing dashboard JavaScript content."""
    return bundle_landing_js()


def bundle_data_shape_config_js() -> str:
    """Concatenates modular data shape planner JavaScript sources on the fly in dependency order."""
    return bundle_js_modules(
        os.path.join(_VIS_DIR, "data_shape"),
        DATA_SHAPE_MODULE_ORDER,
        "cernodata Data Shape Wizard Runtime (Built On The Fly)",
    )


def get_data_shape_config_js() -> str:
    """Retrieves dynamically assembled data shape planner JavaScript content."""
    return bundle_data_shape_config_js()


def get_viewer_js() -> str:
    """Retrieves dynamically assembled interactive visual flow viewer JavaScript content."""
    from src.visualization.viewer.scripts import get_viewer_js as _get_viewer_js

    return _get_viewer_js()


__all__ = [
    "LANDING_MODULE_ORDER",
    "DATA_SHAPE_MODULE_ORDER",
    "bundle_js_modules",
    "bundle_landing_js",
    "get_landing_js",
    "bundle_data_shape_config_js",
    "get_data_shape_config_js",
    "get_viewer_js",
]
