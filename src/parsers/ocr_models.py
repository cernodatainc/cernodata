"""
src/parsers/ocr_models.py

Data structures, result schemas, and coordinate normalization utilities
for targeted section Optical Character Recognition (OCR).
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, TypedDict, Union

from src.dom.bounding_box import BoundingBox


class OCRLine(TypedDict, total=False):
    """
    Structured line item produced by OCR extraction.

    Attributes:
        text: Extracted text content for the line.
        confidence: Normalized confidence score between 0.0 and 1.0.
        bbox: Four-point polygon coordinates [[x0, y0], [x1, y1], [x2, y2], [x3, y3]].
    """

    text: str
    confidence: float
    bbox: Optional[List[List[float]]]


class OCRResult(TypedDict, total=False):
    """
    Standardized OCR extraction result container.

    Attributes:
        success: Whether OCR inference completed without fatal error.
        text: Full extracted text joined across lines.
        confidence: Arithmetic mean confidence score across extracted lines.
        lines: List of structured individual line records.
        error: Error description if extraction failed.
    """

    success: bool
    text: str
    confidence: float
    lines: List[OCRLine]
    error: Optional[str]


def create_ocr_result(
    success: bool = True,
    text: str = "",
    confidence: float = 0.0,
    lines: Optional[List[OCRLine]] = None,
    error: Optional[str] = None,
) -> OCRResult:
    """
    Constructs a standardized OCR result dictionary.

    Args:
        success: True if the operation succeeded, False otherwise.
        text: Aggregated text string.
        confidence: Average confidence value in [0.0, 1.0].
        lines: Sequence of recognized line entries.
        error: Descriptive error message when failure occurs.

    Returns:
        Standardized OCRResult mapping.
    """
    return {
        "success": success,
        "text": text,
        "confidence": confidence,
        "lines": lines if lines is not None else [],
        "error": error,
    }


def normalize_bbox_coords(
    bbox: Union[BoundingBox, dict[str, float], Tuple[float, float, float, float], Sequence[float], List[float]],
) -> Tuple[float, float, float, float]:
    """
    Extracts canonical (x0, y0, x1, y1) coordinates from bounding box representations.

    Supports:
        - BoundingBox domain model objects
        - Dictionaries with (x0, y0, x1, y1) or (left, top, right, bottom)
        - 4-element sequences or tuples

    Args:
        bbox: Bounding box object, dictionary, or sequence.

    Returns:
        Tuple of (x0, y0, x1, y1) floating-point coordinates.

    Raises:
        TypeError: If bbox type is unrecognized or sequence length is insufficient.
    """
    if isinstance(bbox, BoundingBox):
        return float(bbox.x0), float(bbox.y0), float(bbox.x1), float(bbox.y1)

    if isinstance(bbox, dict):
        if "x0" in bbox and "x1" in bbox:
            return (
                float(bbox.get("x0", 0.0)),
                float(bbox.get("y0", 0.0)),
                float(bbox.get("x1", 0.0)),
                float(bbox.get("y1", 0.0)),
            )
        if "left" in bbox and "right" in bbox:
            return (
                float(bbox.get("left", 0.0)),
                float(bbox.get("top", 0.0)),
                float(bbox.get("right", 0.0)),
                float(bbox.get("bottom", 0.0)),
            )
        return (
            float(bbox.get("x0", 0.0)),
            float(bbox.get("y0", 0.0)),
            float(bbox.get("x1", 0.0)),
            float(bbox.get("y1", 0.0)),
        )

    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        return float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])

    raise TypeError(f"Unsupported bounding box coordinate specification: {type(bbox)}")
