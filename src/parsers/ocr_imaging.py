"""
src/parsers/ocr_imaging.py

Image format normalization, memory buffer handling, and PDF region rendering
for section-level OCR extraction.
"""

from __future__ import annotations

import base64
import io
import os
from typing import Sequence, Tuple, Union

import numpy as np
from PIL import Image

from src.dom.bounding_box import BoundingBox
from src.parsers.ocr_models import normalize_bbox_coords
from src.parsers.pdf_utils import HAS_PYPDFIUM, open_pdf


def normalize_to_pil(
    image_input: Union[Image.Image, bytes, bytearray, str, os.PathLike[str], np.ndarray],
) -> Image.Image:
    """
    Normalizes diverse image input formats into a canonical RGB PIL Image.

    Supported inputs:
        - PIL Image (converted directly to RGB mode)
        - Numpy array (2D grayscale or 3D multichannel array)
        - Raw bytes/bytearray buffer (PNG, JPEG, TIFF, etc.)
        - Filesystem path string or PathLike object pointing to an existing file
        - Base64 data URI string ('data:image/png;base64,...') or raw base64 string

    Args:
        image_input: Source image in any supported representation.

    Returns:
        Canonical RGB PIL Image instance.

    Raises:
        ValueError: If base64 payload or file content cannot be parsed.
        TypeError: If input type is unsupported.
    """
    if isinstance(image_input, Image.Image):
        return image_input.convert("RGB")

    if isinstance(image_input, np.ndarray):
        arr = image_input if image_input.ndim == 2 else image_input[:, :, :3]
        return Image.fromarray(arr).convert("RGB")

    if isinstance(image_input, (str, os.PathLike)):
        str_val = os.fspath(image_input).strip()
        if os.path.isfile(str_val):
            return Image.open(str_val).convert("RGB")

        b64_str = str_val
        if "," in b64_str and ";base64" in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        try:
            raw_bytes = base64.b64decode(b64_str)
            return Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        except Exception as ex:
            raise ValueError(f"Unable to parse image from string/path: {ex}") from ex

    if isinstance(image_input, (bytes, bytearray)):
        return Image.open(io.BytesIO(image_input)).convert("RGB")

    raise TypeError(f"Unsupported image input type: {type(image_input)}")


def crop_pdf_region(
    pdf_path: str,
    page_number: int,
    bbox: Union[BoundingBox, dict[str, float], Tuple[float, float, float, float], Sequence[float]],
    scale: float = 2.0,
) -> Image.Image:
    """
    Renders and crops a specific bounding box region from a PDF page into a PIL Image.

    Args:
        pdf_path: Path to the source PDF document.
        page_number: 1-indexed page number.
        bbox: BoundingBox object, coordinate dict, or (x0, y0, x1, y1) sequence.
        scale: Resolution scale factor for rasterization (default 2.0 for OCR clarity).

    Returns:
        Cropped RGB PIL Image corresponding to the requested region.

    Raises:
        RuntimeError: If pypdfium2 is unavailable or page rendering fails.
        FileNotFoundError: If PDF file does not exist on disk.
        ValueError: If bounding box coordinates or cropped dimensions are non-positive.
        IndexError: If page number exceeds total document pages.
    """
    if not HAS_PYPDFIUM:
        raise RuntimeError("pypdfium2 is not installed.")

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

    x0, y0, x1, y1 = normalize_bbox_coords(bbox)
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"Invalid bounding box coordinates: [{x0}, {y0}, {x1}, {y1}]")

    with open_pdf(pdf_path) as pdf:
        if pdf is None:
            raise RuntimeError(f"Failed to open PDF: {pdf_path}")

        page_idx = max(0, page_number - 1)
        if page_idx >= len(pdf):
            raise IndexError(f"Page index {page_number} out of range (total pages: {len(pdf)}).")

        page = pdf[page_idx]
        page_w, page_h = page.get_size()
        try:
            full_pil = page.render(scale=scale).to_pil().convert("RGB")
        except Exception as ex:
            raise RuntimeError(f"Failed to render page: {ex}") from ex

    scale_x = full_pil.width / page_w
    scale_y = full_pil.height / page_h

    crop_x0 = max(0, int(round(x0 * scale_x)))
    crop_y0 = max(0, int(round(y0 * scale_y)))
    crop_x1 = min(full_pil.width, int(round(x1 * scale_x)))
    crop_y1 = min(full_pil.height, int(round(y1 * scale_y)))

    if crop_x1 <= crop_x0 or crop_y1 <= crop_y0:
        raise ValueError("Cropped bounding box is empty after scaling.")

    return full_pil.crop((crop_x0, crop_y0, crop_x1, crop_y1))
