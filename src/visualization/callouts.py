"""
src/visualization/callouts.py

Red quality violation callout badge renderer for bounding box overlays.
"""

from typing import List, Dict, Any
from PIL import ImageDraw, ImageFont


def draw_violation_callout(
    draw_base: ImageDraw.ImageDraw,
    x0: float,
    badge_y1: float,
    violation: Dict[str, Any],
    font: ImageFont.ImageFont
):
    """Draws red callout marker badge for a quality violation."""
    snippet = violation.get("detected_snippet", "")
    suggested = violation.get("suggested_correction", "")
    viol_label = f"[!] VIOLATION: '{snippet}'"
    if suggested:
        viol_label += f" -> '{suggested}'"

    v_left, v_top, v_right, v_bottom = font.getbbox(viol_label)
    v_w = v_right - v_left
    v_h = v_bottom - v_top

    v_x0 = x0
    v_y0 = badge_y1 + 2
    v_x1 = v_x0 + v_w + 10
    v_y1 = v_y0 + v_h + 6

    draw_base.rectangle([v_x0, v_y0, v_x1, v_y1], fill="#D50000", outline="yellow", width=1)
    draw_base.text((v_x0 + 5, v_y0 + 3), viol_label, fill="white", font=font)
