"""
src/parsers/section_ocr.py

Targeted OCR parser for document sections, cutouts, and bounding box regions.
Uses RapidOCR with PyTorch CPU backend by default, with support for base64 cutouts,
PDF crops, and extensible custom OCR engine backends.
"""

from __future__ import annotations

import os
from typing import Any, Callable, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image

from src.dom.bounding_box import BoundingBox
from src.parsers.ocr_imaging import crop_pdf_region, normalize_to_pil
from src.parsers.ocr_models import (
    OCRLine,
    OCRResult,
    create_ocr_result,
    normalize_bbox_coords,
)

HAS_RAPIDOCR = False
try:
    from rapidocr import EngineType, RapidOCR

    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False


class SectionOCRParser:
    """
    Parser for executing targeted OCR extraction on document sections,
    cutout images, or bounding box coordinates.

    Supports custom OCR engines and factories via dependency injection,
    making it straightforward to test with lightweight mocks or swap engines.
    """

    def __init__(
        self,
        language: Optional[str] = "en",
        engine: Optional[Any] = None,
        engine_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.language: str = language.lower().strip() if language else ""
        self._engine: Optional[Any] = engine
        self._engine_factory: Optional[Callable[[], Any]] = engine_factory
        self._init_attempted: bool = engine is not None

    @property
    def engine(self) -> Optional[Any]:
        """Returns the underlying OCR engine, lazily initializing if needed."""
        return self._get_engine()

    @engine.setter
    def engine(self, value: Optional[Any]) -> None:
        """Sets or replaces the underlying OCR engine."""
        self._engine = value
        self._init_attempted = True

    def _create_default_engine(self) -> Optional[Any]:
        """Initializes the default RapidOCR PyTorch CPU engine."""
        if not HAS_RAPIDOCR:
            return None
        try:
            return RapidOCR(
                params={
                    "Det.engine_type": EngineType.TORCH,
                    "Cls.engine_type": EngineType.TORCH,
                    "Rec.engine_type": EngineType.TORCH,
                }
            )
        except Exception as ex:
            print(f"[WARN] RapidOCR torch engine initialization failed: {ex}")
            try:
                return RapidOCR()
            except Exception:
                return None

    def _create_engine(self) -> Optional[Any]:
        """Creates engine using registered engine_factory or fallback default."""
        if self._engine_factory is not None:
            try:
                return self._engine_factory()
            except Exception as ex:
                print(f"[WARN] Custom OCR engine factory failed: {ex}")
                return None
        return self._create_default_engine()

    def _get_engine(self) -> Optional[Any]:
        if not self._init_attempted:
            self._init_attempted = True
            if self._engine is None:
                self._engine = self._create_engine()
        return self._engine

    def _run_engine(self, engine: Any, pil_image: Image.Image) -> Any:
        """Executes raw inference with the underlying OCR engine on a PIL Image."""
        return engine(np.array(pil_image))

    def _parse_engine_result(self, result: Any) -> Tuple[str, float, List[OCRLine]]:
        """
        Extracts and standardizes raw OCR engine output into joined text,
        average confidence score, and structured line records.
        """
        if result is None:
            return "", 0.0, []

        txts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)
        boxes = getattr(result, "boxes", None)

        if txts is None and isinstance(result, dict):
            txts = result.get("txts")
            scores = result.get("scores")
            boxes = result.get("boxes")

        if txts is None and isinstance(result, (list, tuple)) and len(result) > 0:
            first = result[0]
            if isinstance(first, (list, tuple)):
                parsed_txts: List[Any] = []
                parsed_scores: List[Any] = []
                parsed_boxes: List[Any] = []
                for entry in first:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                        parsed_boxes.append(entry[0])
                        if len(entry) == 2 and isinstance(entry[1], (list, tuple)):
                            parsed_txts.append(entry[1][0])
                            parsed_scores.append(entry[1][1] if len(entry[1]) > 1 else 1.0)
                        elif len(entry) >= 3:
                            parsed_txts.append(entry[1])
                            parsed_scores.append(entry[2])
                txts = parsed_txts
                scores = parsed_scores
                boxes = parsed_boxes

        if not txts:
            return "", 0.0, []

        lines: List[OCRLine] = []
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
                "bbox": box_coords,
            })

        joined_text = "\n".join([line["text"] for line in lines])
        avg_confidence = round(sum(valid_scores) / len(valid_scores), 4) if valid_scores else 0.0

        return joined_text, avg_confidence, lines

    def parse_image(
        self,
        image_input: Union[Image.Image, bytes, bytearray, str, os.PathLike[str], np.ndarray],
        language: Optional[str] = None,
    ) -> OCRResult:
        """
        Parses an image containing a document section using OCR.

        Accepts:
            - PIL Image object
            - Raw image bytes/bytearray (PNG, JPEG, etc.)
            - File path string or Path object
            - Base64 data URI string ('data:image/png;base64,...') or raw base64 string
            - Numpy array (RGB or Grayscale)

        Returns a dictionary with:
            - success (bool)
            - text (str): joined raw text
            - confidence (float): average confidence score [0.0 - 1.0]
            - lines (list[OCRLine]): per-line text, scores, and bounding boxes
            - error (Optional[str])
        """
        try:
            pil_img = normalize_to_pil(image_input)
        except TypeError as ex:
            return create_ocr_result(success=False, error=str(ex))
        except Exception as ex:
            return create_ocr_result(success=False, error=f"Failed to load image: {str(ex)}")

        if pil_img.width <= 0 or pil_img.height <= 0:
            return create_ocr_result(success=False, error="Image is empty or has invalid dimensions.")

        engine = self._get_engine()
        if engine is None:
            return create_ocr_result(success=True, error="OCR engine not available.")

        try:
            result = self._run_engine(engine, pil_img)
        except Exception as ex:
            return create_ocr_result(success=False, error=f"OCR inference error: {str(ex)}")

        joined_text, avg_confidence, lines = self._parse_engine_result(result)
        return create_ocr_result(
            success=True,
            text=joined_text,
            confidence=avg_confidence,
            lines=lines,
        )

    def crop_section_image(
        self,
        pdf_path: str,
        page_number: int,
        bbox: Union[BoundingBox, dict[str, float], Tuple[float, float, float, float], Sequence[float]],
        scale: float = 2.0,
    ) -> Image.Image:
        """Extracts and crops an image region from a PDF page."""
        return crop_pdf_region(pdf_path, page_number, bbox, scale=scale)

    def parse_section_from_pdf(
        self,
        pdf_path: str,
        page_number: int,
        bbox: Union[BoundingBox, dict[str, float], Tuple[float, float, float, float], Sequence[float]],
        language: Optional[str] = None,
        scale: float = 2.0,
    ) -> OCRResult:
        """
        Extracts and crops a specific section bounding box from a PDF page and runs OCR.

        Args:
            pdf_path: Path to the source PDF.
            page_number: 1-indexed page number.
            bbox: BoundingBox object, coordinate dict, or tuple/list.
            language: Optional OCR language code override.
            scale: Resolution scale factor for PDF rendering (default 2.0 for high fidelity).
        """
        try:
            cropped_img = self.crop_section_image(pdf_path, page_number, bbox, scale=scale)
        except (FileNotFoundError, ValueError, IndexError, RuntimeError) as ex:
            return create_ocr_result(success=False, error=str(ex))
        except Exception as ex:
            return create_ocr_result(success=False, error=f"Failed to crop PDF section: {str(ex)}")

        return self.parse_image(cropped_img, language=language)


_default_parser: Optional[SectionOCRParser] = None


def get_default_section_parser() -> SectionOCRParser:
    """Returns a singleton instance of SectionOCRParser."""
    global _default_parser
    if _default_parser is None:
        _default_parser = SectionOCRParser()
    return _default_parser


def set_default_section_parser(parser: Optional[SectionOCRParser]) -> None:
    """Sets or resets the default SectionOCRParser singleton instance."""
    global _default_parser
    _default_parser = parser


def parse_image_ocr(
    image_input: Union[Image.Image, bytes, bytearray, str, os.PathLike[str], np.ndarray],
    language: str = "en",
) -> OCRResult:
    """Module-level convenience function for targeted image OCR."""
    parser = get_default_section_parser()
    return parser.parse_image(image_input, language=language)


def parse_section_from_pdf(
    pdf_path: str,
    page_number: int,
    bbox: Union[BoundingBox, dict[str, float], Tuple[float, float, float, float], Sequence[float]],
    language: str = "en",
    scale: float = 2.0,
) -> OCRResult:
    """Module-level convenience function for cropping a section from a PDF and running OCR."""
    parser = get_default_section_parser()
    return parser.parse_section_from_pdf(pdf_path, page_number, bbox, language=language, scale=scale)


__all__ = [
    "OCRLine",
    "OCRResult",
    "SectionOCRParser",
    "create_ocr_result",
    "crop_pdf_region",
    "get_default_section_parser",
    "normalize_bbox_coords",
    "normalize_to_pil",
    "parse_image_ocr",
    "parse_section_from_pdf",
    "set_default_section_parser",
]
