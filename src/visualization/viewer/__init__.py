"""
src/visualization/viewer/__init__.py

Interactive viewer subpackage components.
"""

from __future__ import annotations

from src.visualization.viewer.pdf_renderer import (
    get_pdf_page_dimensions,
    page_to_base64,
    render_all_pages_to_base64,
)
from src.visualization.viewer.scripts import (
    build_viewer_script,
    bundle_viewer_js,
    get_viewer_js,
)
from src.visualization.viewer.styles import (
    VIEWER_CSS,
    get_viewer_css,
)
from src.visualization.viewer.templates import (
    build_timeline_buttons,
    build_viewer_html,
    generate_interactive_html,
    get_viewer_template,
)

__all__ = [
    "page_to_base64",
    "get_pdf_page_dimensions",
    "render_all_pages_to_base64",
    "VIEWER_CSS",
    "get_viewer_css",
    "build_viewer_script",
    "bundle_viewer_js",
    "get_viewer_js",
    "build_timeline_buttons",
    "build_viewer_html",
    "generate_interactive_html",
    "get_viewer_template",
]
