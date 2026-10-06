"""
src/visualization/bundler.py

On-the-fly JavaScript bundle builder for cernodata web visualization interfaces.
Concatenates modular concern scripts at runtime without persisting bundled assets on disk.
"""

from __future__ import annotations

import os
from typing import List

_VIS_DIR: str = os.path.dirname(os.path.abspath(__file__))

LANDING_MODULE_ORDER: List[str] = [
    "utils.js",
    "navigation.js",
    "execution.js",
    "runs.js",
    "results.js",
    "matrix_grid.js",
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


def bundle_landing_js() -> str:
    """
    Concatenates modular landing page JavaScript sources on the fly in dependency order.

    Returns:
        Complete client JavaScript payload for the ingestion dashboard.
    """
    landing_dir = os.path.join(_VIS_DIR, "landing")
    parts: List[str] = [
        "/* ==========================================================================\n"
        " * cernodata Ingestion Hub Dashboard Runtime (Built On The Fly)\n"
        " * ========================================================================== */\n"
    ]
    for mod_name in LANDING_MODULE_ORDER:
        mod_path = os.path.join(landing_dir, mod_name)
        if os.path.exists(mod_path):
            with open(mod_path, "r", encoding="utf-8") as f:
                parts.append(f"/* === Concern Module: {mod_name} === */\n" + f.read())
    return "\n\n".join(parts)


def get_landing_js() -> str:
    """
    Retrieves dynamically assembled landing dashboard JavaScript content.

    Returns:
        JavaScript source string assembled on the fly.
    """
    return bundle_landing_js()


def bundle_data_shape_config_js() -> str:
    """
    Concatenates modular data shape planner JavaScript sources on the fly in dependency order.

    Returns:
        Complete client JavaScript payload for the data shape wizard.
    """
    data_shape_dir = os.path.join(_VIS_DIR, "data_shape")
    parts: List[str] = [
        "/* ==========================================================================\n"
        " * cernodata Data Shape Wizard Runtime (Built On The Fly)\n"
        " * ========================================================================== */\n"
    ]
    for mod_name in DATA_SHAPE_MODULE_ORDER:
        mod_path = os.path.join(data_shape_dir, mod_name)
        if os.path.exists(mod_path):
            with open(mod_path, "r", encoding="utf-8") as f:
                parts.append(f"/* === Concern Module: {mod_name} === */\n" + f.read())
    return "\n\n".join(parts)


def get_data_shape_config_js() -> str:
    """
    Retrieves dynamically assembled data shape planner JavaScript content.

    Returns:
        JavaScript source string assembled on the fly.
    """
    return bundle_data_shape_config_js()


def get_viewer_js() -> str:
    """
    Retrieves dynamically assembled interactive visual flow viewer JavaScript content.

    Returns:
        JavaScript source string assembled on the fly.
    """
    from src.visualization.viewer.scripts import get_viewer_js as _get_viewer_js

    return _get_viewer_js()


__all__ = [
    "LANDING_MODULE_ORDER",
    "DATA_SHAPE_MODULE_ORDER",
    "bundle_landing_js",
    "get_landing_js",
    "bundle_data_shape_config_js",
    "get_data_shape_config_js",
    "get_viewer_js",
]
