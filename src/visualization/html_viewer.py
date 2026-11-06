"""
src/visualization/html_viewer.py

Interactive HTML Visual Flow App & Live Step-by-Step Preset Explorer.
Re-exports generate_interactive_html from src.visualization.viewer.
"""

from __future__ import annotations

from src.visualization.viewer import generate_interactive_html

__all__ = ["generate_interactive_html"]
