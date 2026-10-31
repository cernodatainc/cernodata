"""
src/pipeline/server/page_images.py

Page image and page dimension loading for the interactive viewer, with
fallbacks to cached viewer HTML metadata and pre-rendered overlay images.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Dict, List, Tuple

logger = logging.getLogger("cernodata.server.page_images")

A4_WIDTH_PT = 595.28
A4_HEIGHT_PT = 841.89


def _render_from_pdf(
    pdf_path: str, total_pages: int
) -> Tuple[List[str], List[Dict[str, float]]]:
    """Renders pages directly from the source PDF; returns empty lists on failure."""
    if not (pdf_path and os.path.exists(pdf_path)):
        return [], []
    try:
        from src.visualization.viewer.pdf_renderer import (
            get_pdf_page_dimensions,
            render_all_pages_to_base64,
        )

        images = render_all_pages_to_base64(pdf_path, total_pages=total_pages)
        dims = get_pdf_page_dimensions(pdf_path)
        return images, dims
    except Exception as e:
        logger.warning("Could not render page images for %s: %s", pdf_path, e)
        return [], []


def _dimensions_from_viewer_html(target_dir: str) -> List[Dict[str, float]]:
    """Parses embedded pageDimensions from a previously generated viewer HTML file."""
    viewer_html_path = os.path.join(target_dir, "interactive_viewer.html")
    if not os.path.exists(viewer_html_path):
        return []
    try:
        with open(viewer_html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        dim_match = re.search(r"pageDimensions:\s*(\[[^\]]*\])", html_content)
        if dim_match:
            parsed_dims = json.loads(dim_match.group(1))
            if isinstance(parsed_dims, list) and len(parsed_dims) > 0:
                return parsed_dims
    except Exception as e:
        logger.debug("Could not parse pageDimensions from interactive_viewer.html: %s", e)
    return []


def _load_overlay_images(
    target_dir: str,
    total_pages: int,
    page_dimensions: List[Dict[str, float]],
) -> List[str]:
    """Loads pre-rendered overlay PNGs as data URIs, filling missing page dimensions."""
    from PIL import Image

    page_images: List[str] = []
    for p in range(1, total_pages + 1):
        img_candidate = os.path.join(target_dir, f"overlay_page_{p}.png")
        if not os.path.exists(img_candidate):
            continue
        try:
            with open(img_candidate, "rb") as img_f:
                b64 = base64.b64encode(img_f.read()).decode("ascii")
                page_images.append(f"data:image/png;base64,{b64}")

            if len(page_dimensions) < p:
                with Image.open(img_candidate) as pil_img:
                    w_px, h_px = pil_img.size
                    # Default PageVisualizer scale is 150 DPI / 72.0 points
                    page_dimensions.append({
                        "width": round(w_px * 72.0 / 150.0, 2),
                        "height": round(h_px * 72.0 / 150.0, 2),
                    })
        except Exception as e:
            logger.warning("Could not load overlay image %s: %s", img_candidate, e)
    return page_images


def load_or_render_page_images(
    pdf_path: str,
    target_dir: str,
    total_pages: int,
) -> Tuple[List[str], List[Dict[str, float]]]:
    """
    Renders PDF pages to base64 images and gets dimensions, falling back
    to pre-rendered overlay image files if direct rendering fails or is unavailable.

    Args:
        pdf_path: Path to source PDF document.
        target_dir: Output directory containing cached overlay images.
        total_pages: Expected page count.

    Returns:
        Tuple of (page_images_base64_list, page_dimensions_list).
    """
    page_images, page_dimensions = _render_from_pdf(pdf_path, total_pages)

    if not page_dimensions:
        page_dimensions = _dimensions_from_viewer_html(target_dir)

    if not page_images:
        page_images = _load_overlay_images(target_dir, total_pages, page_dimensions)

    # Final safety fallback to standard A4
    while len(page_dimensions) < len(page_images):
        page_dimensions.append({"width": A4_WIDTH_PT, "height": A4_HEIGHT_PT})

    return page_images, page_dimensions
