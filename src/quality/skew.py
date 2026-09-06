"""
src/quality/skew.py

Local Text Alignment Skew Detector.
Uses OpenCV minimum-area oriented bounding box analysis (cv2.minAreaRect) to detect local text line
skew angles (theta_skew) and align bounding boxes to tilted document text.
"""

import os
from typing import Dict, Any, List, Optional
import numpy as np

HAS_CV2 = False
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

HAS_PYPDFIUM = False
try:
    import pypdfium2
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False

from src.dom import DocumentDOM, DOMNode


def _extract_contour_angles(crop_np: np.ndarray) -> List[float]:
    """Extracts text line contour minimum area rectangle angles from image crop."""
    gray = cv2.cvtColor(crop_np, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    angles = []

    for c in contours:
        if cv2.contourArea(c) > 30:
            rect = cv2.minAreaRect(c)
            angle = rect[-1]
            if angle < -45:
                angle = 90 + angle
            elif angle > 45:
                angle = angle - 90
            
            if -30.0 <= angle <= 30.0:
                angles.append(angle)

    return angles


def _compute_median_skew_angle(angles: List[float]) -> float:
    """Calculates median text skew angle from contour angles list."""
    if not angles:
        return 0.0
    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.4:
        return 0.0
    return round(median_angle, 2)


def detect_node_text_skew(crop_np: np.ndarray) -> float:
    """
    Analyzes a numpy RGB crop of a text node to determine its local text line orientation angle (in degrees).
    Returns float angle in range [-45.0, 45.0].
    """
    if not HAS_CV2 or crop_np is None or crop_np.size == 0:
        return 0.0

    height, width = crop_np.shape[:2]
    if height < 10 or width < 10:
        return 0.0

    angles = _extract_contour_angles(crop_np)
    return _compute_median_skew_angle(angles)


def apply_text_skew_alignment(dom: DocumentDOM, pdf_path: str, scale: float = 150/72.0) -> DocumentDOM:
    """
    Scans PDF page images for each node in DocumentDOM and calculates local text skew angles,
    updating node bounding box orientation angles.
    """
    if not HAS_CV2 or not HAS_PYPDFIUM or not os.path.exists(pdf_path):
        return dom

    try:
        pdf = pypdfium2.PdfDocument(pdf_path)
        page_images: Dict[int, np.ndarray] = {}

        for page_idx in range(len(pdf)):
            page_no = page_idx + 1
            pdf_page = pdf[page_idx]
            page_w, page_h = pdf_page.get_size()

            pil_img = pdf_page.render(scale=scale).to_pil().convert("RGB")
            img_np = np.array(pil_img)

            sx = img_np.shape[1] / page_w if page_w > 0 else scale
            sy = img_np.shape[0] / page_h if page_h > 0 else scale

            page_images[page_no] = (img_np, sx, sy)

        for node in dom.nodes:
            page_no = node.global_page_index
            if page_no in page_images:
                img_np, sx, sy = page_images[page_no]
                bbox = node.bounding_box

                x0 = int(max(0, bbox.x0 * sx))
                y0 = int(max(0, bbox.y0 * sy))
                x1 = int(min(img_np.shape[1], bbox.x1 * sx))
                y1 = int(min(img_np.shape[0], bbox.y1 * sy))

                if (x1 - x0) > 15 and (y1 - y0) > 10:
                    crop = img_np[y0:y1, x0:x1]
                    skew_angle = detect_node_text_skew(crop)
                    if skew_angle != 0.0:
                        node.bounding_box.angle = skew_angle

    except Exception as e:
        print(f"[WARN] Text skew alignment error ({e}), keeping unaligned bounding boxes.")

    return dom
