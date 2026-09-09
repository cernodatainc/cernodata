"""
src/visualization/badges.py

Bottom-left confidence score & violation summary badge renderer.
"""

from typing import List, Dict, Any, Optional
from PIL import ImageDraw, ImageFont
from src.dom import DOMNode
from src.quality import evaluate_page_confidence


def draw_score_badge_bottom_left(
    draw: ImageDraw.ImageDraw,
    img_w: int,
    img_h: int,
    page_no: int,
    nodes: List[DOMNode],
    violations: List[Dict[str, Any]],
    font: ImageFont.ImageFont,
    header_font: ImageFont.ImageFont,
    confidence_score: Optional[float] = None
):
    """Renders overall confidence score & violation summary badge in bottom-left corner."""
    if confidence_score is not None:
        page_score = float(confidence_score)
    else:
        page_score = float(evaluate_page_confidence(nodes))
    status_text = "ACCEPT" if page_score >= 0.82 else "FALLBACK"
    status_color = "#00E676" if page_score >= 0.82 else "#FF5252"

    line1 = f"Page {page_no} Confidence Score: {page_score:.4f}"
    line2 = f"Decision Status: {status_text} | Violations Flagged: {len(violations)}"

    l1_bbox = header_font.getbbox(line1)
    l2_bbox = font.getbbox(line2)

    w1 = l1_bbox[2] - l1_bbox[0]
    w2 = l2_bbox[2] - l2_bbox[0]
    badge_w = max(w1, w2) + 24
    badge_h = 54

    margin = 16
    bx0 = margin
    by1 = img_h - margin
    by0 = by1 - badge_h
    bx1 = bx0 + badge_w

    draw.rectangle([bx0, by0, bx1, by1], fill="#111827", outline=status_color, width=2)
    draw.text((bx0 + 12, by0 + 8), line1, fill="white", font=header_font)
    draw.text((bx0 + 12, by0 + 28), line2, fill=status_color, font=font)
