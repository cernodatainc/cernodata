"""
src/parsers/section_ocr.py

Targeted OCR parser for document sections, cutouts, and bounding box regions.
Uses RapidOCR with PyTorch CPU backend, with support for base64 cutouts and PDF crops.
"""

import os
import io
import re
import base64
from typing import Dict, Any, List, Optional, Union, Tuple
from PIL import Image
import numpy as np

from src.dom.bounding_box import BoundingBox

HAS_RAPIDOCR = False
try:
    from rapidocr import RapidOCR, EngineType
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False

HAS_PYPDFIUM = False
try:
    import pypdfium2
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False


def _ocr_result(
    success: bool = True,
    text: str = "",
    confidence: float = 0.0,
    lines: Optional[List[Dict[str, Any]]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Constructs a standardized OCR result dictionary."""
    return {
        "success": success,
        "text": text,
        "confidence": confidence,
        "lines": lines or [],
        "error": error,
    }


def _normalize_to_pil(image_input: Union[Image.Image, bytes, str, np.ndarray]) -> Image.Image:
    """Normalizes supported image inputs (PIL, numpy, bytes, base64) to an RGB PIL Image."""
    if isinstance(image_input, Image.Image):
        return image_input.convert("RGB")
    if isinstance(image_input, np.ndarray):
        arr = image_input if image_input.ndim == 2 else image_input[:, :, :3]
        return Image.fromarray(arr).convert("RGB")
    if isinstance(image_input, str):
        b64_str = image_input.strip()
        if "," in b64_str and ";base64" in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        image_input = base64.b64decode(b64_str)
    if isinstance(image_input, (bytes, bytearray)):
        return Image.open(io.BytesIO(image_input)).convert("RGB")
    raise TypeError(f"Unsupported image input type: {type(image_input)}")


class SectionOCRParser:
    """
    Parser for executing targeted OCR extraction on document sections,
    cutout images, or bounding box coordinates.
    """

    def __init__(self, language: str = "en"):
        self.language = language.lower().strip()
        self._engine: Optional[Any] = None
        self._init_attempted = False

    def _get_engine(self) -> Optional[Any]:
        if not self._init_attempted:
            self._init_attempted = True
            if HAS_RAPIDOCR:
                try:
                    self._engine = RapidOCR(
                        params={
                            "Det.engine_type": EngineType.TORCH,
                            "Cls.engine_type": EngineType.TORCH,
                            "Rec.engine_type": EngineType.TORCH,
                        }
                    )
                except Exception as ex:
                    print(f"[WARN] RapidOCR torch engine initialization failed: {ex}")
                    try:
                        self._engine = RapidOCR()
                    except Exception:
                        self._engine = None
        return self._engine

    def parse_image(
        self,
        image_input: Union[Image.Image, bytes, str, np.ndarray],
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parses an image containing a document section using OCR.

        Accepts:
            - PIL Image object
            - Raw image bytes (PNG, JPEG, etc.)
            - Base64 data URI string ('data:image/png;base64,...') or raw base64 string
            - Numpy array (RGB or Grayscale)

        Returns a dictionary with:
            - success (bool)
            - text (str): joined raw text
            - confidence (float): average confidence score [0.0 - 1.0]
            - lines (List[Dict[str, Any]]): per-line text, scores, and bounding boxes
            - error (Optional[str])
        """
        try:
            pil_img = _normalize_to_pil(image_input)
        except TypeError as ex:
            return _ocr_result(success=False, error=str(ex))
        except Exception as ex:
            return _ocr_result(success=False, error=f"Failed to load image: {str(ex)}")

        if pil_img.width <= 0 or pil_img.height <= 0:
            return _ocr_result(success=False, error="Image is empty or has invalid dimensions.")

        engine = self._get_engine()
        if engine is None:
            return _ocr_result(success=True, error="OCR engine not available.")

        try:
            result = engine(np.array(pil_img))
        except Exception as ex:
            return _ocr_result(success=False, error=f"OCR inference error: {str(ex)}")

        txts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        boxes = getattr(result, "boxes", None)

        if not txts:
            return _ocr_result(success=True)

        lines: List[Dict[str, Any]] = []
        valid_scores: List[float] = []

        txt_list = list(txts) if isinstance(txts, (list, tuple)) else [str(txts)]
        score_list = list(scores) if isinstance(scores, (list, tuple)) else [1.0] * len(txt_list)
        box_list = list(boxes) if isinstance(boxes, (list, tuple, np.ndarray)) else [None] * len(txt_list)

        for i, text_val in enumerate(txt_list):
            clean_text = str(text_val).strip()
            if not clean_text:
                continue

            sc = float(score_list[i]) if i < len(score_list) and score_list[i] is not None else 1.0
            valid_scores.append(sc)

            box_val = box_list[i] if i < len(box_list) else None
            box_coords: Optional[List[List[float]]] = None
            if box_val is not None:
                try:
                    box_coords = [[float(p[0]), float(p[1])] for p in box_val]
                except Exception:
                    box_coords = None

            lines.append({
                "text": clean_text,
                "confidence": round(sc, 4),
                "bbox": box_coords
            })

        joined_text = "\n".join([line["text"] for line in lines])
        avg_confidence = round(sum(valid_scores) / len(valid_scores), 4) if valid_scores else 0.0

        return _ocr_result(
            success=True,
            text=joined_text,
            confidence=avg_confidence,
            lines=lines
        )

    def parse_section_from_pdf(
        self,
        pdf_path: str,
        page_number: int,
        bbox: Union[BoundingBox, Dict[str, float]],
        language: Optional[str] = None,
        scale: float = 2.0
    ) -> Dict[str, Any]:
        """
        Extracts and crops a specific section bounding box from a PDF page and runs OCR.

        Args:
            pdf_path: Path to the source PDF.
            page_number: 1-indexed page number.
            bbox: BoundingBox object or dict with x0, y0, x1, y1.
            language: Optional OCR language code override.
            scale: Resolution scale factor for PDF rendering (default 2.0 for high fidelity).
        """
        if not HAS_PYPDFIUM:
            return _ocr_result(success=False, error="pypdfium2 is not installed.")

        if not os.path.exists(pdf_path):
            return _ocr_result(success=False, error=f"PDF file does not exist: {pdf_path}")

        if isinstance(bbox, dict):
            x0 = float(bbox.get("x0", 0.0))
            y0 = float(bbox.get("y0", 0.0))
            x1 = float(bbox.get("x1", 0.0))
            y1 = float(bbox.get("y1", 0.0))
        else:
            x0, y0, x1, y1 = bbox.x0, bbox.y0, bbox.x1, bbox.y1

        if x1 <= x0 or y1 <= y0:
            return _ocr_result(success=False, error=f"Invalid bounding box coordinates: [{x0}, {y0}, {x1}, {y1}]")

        try:
            pdf = pypdfium2.PdfDocument(pdf_path)
            page_idx = max(0, page_number - 1)
            if page_idx >= len(pdf):
                return _ocr_result(
                    success=False,
                    error=f"Page index {page_number} out of range (total pages: {len(pdf)})."
                )

            page = pdf[page_idx]
            page_w, page_h = page.get_size()

            # Render full page at desired scale
            full_pil = page.render(scale=scale).to_pil().convert("RGB")

            # Calculate crop box in rendered pixel coordinates
            scale_x = full_pil.width / page_w
            scale_y = full_pil.height / page_h

            crop_x0 = max(0, int(round(x0 * scale_x)))
            crop_y0 = max(0, int(round(y0 * scale_y)))
            crop_x1 = min(full_pil.width, int(round(x1 * scale_x)))
            crop_y1 = min(full_pil.height, int(round(y1 * scale_y)))

            if crop_x1 <= crop_x0 or crop_y1 <= crop_y0:
                return _ocr_result(success=False, error="Cropped bounding box is empty after scaling.")

            cropped_img = full_pil.crop((crop_x0, crop_y0, crop_x1, crop_y1))
            return self.parse_image(cropped_img, language=language)

        except Exception as ex:
            return _ocr_result(success=False, error=f"Failed to crop and parse PDF section: {str(ex)}")


_default_parser: Optional[SectionOCRParser] = None


def get_default_section_parser() -> SectionOCRParser:
    """Returns a singleton instance of SectionOCRParser."""
    global _default_parser
    if _default_parser is None:
        _default_parser = SectionOCRParser()
    return _default_parser


def parse_image_ocr(
    image_input: Union[Image.Image, bytes, str, np.ndarray],
    language: str = "en"
) -> Dict[str, Any]:
    """Module-level convenience function for targeted image OCR."""
    parser = get_default_section_parser()
    return parser.parse_image(image_input, language=language)


def parse_section_from_pdf(
    pdf_path: str,
    page_number: int,
    bbox: Union[BoundingBox, Dict[str, float]],
    language: str = "en",
    scale: float = 2.0
) -> Dict[str, Any]:
    """Module-level convenience function for cropping a section from a PDF and running OCR."""
    parser = get_default_section_parser()
    return parser.parse_section_from_pdf(pdf_path, page_number, bbox, language=language, scale=scale)
