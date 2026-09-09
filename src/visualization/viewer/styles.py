"""
src/visualization/viewer/styles.py

CSS styles loader for interactive HTML visual flow explorer.
Loads stylesheet from viewer.css on demand.
"""

import os

_CSS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer.css")


def get_viewer_css() -> str:
    """Returns CSS content from viewer.css."""
    with open(_CSS_PATH, "r", encoding="utf-8") as f:
        return f.read()


VIEWER_CSS = get_viewer_css()
