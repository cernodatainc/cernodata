"""
src/parsers/section_ocr.py

Targeted OCR parser for document sections, cutouts, and bounding box regions.
Uses RapidOCR with PyTorch CPU backend by default, with support for base64 cutouts,
PDF crops, and extensible custom OCR engine backends.
"""

from __future__ import annotations

import base64
import io
import os
from typing import Any, Callable, Optional, TypedDict, Union
from PIL import Image
import numpy as np

from src.dom.bounding_box import BoundingBox
from src.parsers.pdf_utils import open_pdf, HAS_PYPDFIUM

HAS_RAPIDOCR = False
try:
    from rapidocr import RapidOCR, EngineType
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False


class OCRLine(TypedDict, total=False):
    """Structured line item produced by OCR extraction."""
    text: str
    confidence: float
    bbox: Optional[list[list[float]]]


class OCRResult(TypedDict, total=False):
    """Standardized OCR extraction result container."""
    success: bool
    text: str
    confidence: float
    lines: list[OCRLine]
    error: Optional[str]


def create_ocr_result(
    success: bool = True,
    text: str = "",
    confidence: float = 0.0,
    lines: Optional[list[OCRLine]] = None,
    error: Optional[str] = None,
) -> OCRResult:
    """Constructs a standardized OCR result dictionary."""
    return {
        "success": success,
        "text": text,
        "confidence": confidence,
        "lines": lines if lines is not None else [],
        "error": error,
    }


# Backwards compatibility alias
_ocr_result = create_ocr_result


def normalize_to_pil(
    image_input: Union[Image.Image, bytes, bytearray, str, os.PathLike[str], np.ndarray]
) -> Image.Image:
    """
    Normalizes supported image inputs to an RGB PIL Image.

    Supported inputs:
        - PIL Image (converted to RGB)
        - Numpy array (2D grayscale or 3D RGB)
        - Raw bytes/bytearray (PNG, JPEG, etc.)
        - File system path (str or os.PathLike) pointing to an existing image file
        - Base64 data URI string ('data:image/png;base64,...') or raw base64 string
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


# Backwards compatibility alias
_normalize_to_pil = normalize_to_pil


def normalize_bbox_coords(
    bbox: Union[BoundingBox, dict[str, float], tuple[float, float, float, float], list[float]]
) -> tuple[float, float, float, float]:
    """
    Extracts (x0, y0, x1, y1) coordinates from BoundingBox, coordinate dictionary, or 4-element sequence.
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


def crop_pdf_region(
    pdf_path: str,
    page_number: int,
    bbox: Union[BoundingBox, dict[str, float], tuple[float, float, float, float], list[float]],
    scale: float = 2.0,
) -> Image.Image:
    """
    Renders and crops a specific bounding box region from a PDF page into a PIL Image.

    Args:
        pdf_path: Path to the source PDF.
        page_number: 1-indexed page number.
        bbox: BoundingBox object, coordinate dict, or (x0, y0, x1, y1) tuple/list.
        scale: Resolution scale factor for rendering.

    Returns:
        RGB PIL Image of the cropped region.

    Raises:
        RuntimeError: If pypdfium2 is unavailable or rendering fails.
        FileNotFoundError: If PDF file does not exist.
        ValueError: If bounding box coordinates or page number are invalid.
        IndexError: If page index is out of range.
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
        self.language = language.lower().strip() if language else ""
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

    def _parse_engine_result(self, result: Any) -> tuple[str, float, list[OCRLine]]:
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
                parsed_txts = []
                parsed_scores = []
                parsed_boxes = []
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

        lines: list[OCRLine] = []
        valid_scores: list[float] = []

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
            box_coords: Optional[list[list[float]]] = None
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
        language: Optional[str] = None
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
            lines=lines
        )

    def crop_section_image(
        self,
        pdf_path: str,
        page_number: int,
        bbox: Union[BoundingBox, dict[str, float], tuple[float, float, float, float], list[float]],
        scale: float = 2.0
    ) -> Image.Image:
        """Extracts and crops an image region from a PDF page."""
        return crop_pdf_region(pdf_path, page_number, bbox, scale=scale)

    def parse_section_from_pdf(
        self,
        pdf_path: str,
        page_number: int,
        bbox: Union[BoundingBox, dict[str, float], tuple[float, float, float, float], list[float]],
        language: Optional[str] = None,
        scale: float = 2.0
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
    language: str = "en"
) -> OCRResult:
    """Module-level convenience function for targeted image OCR."""
    parser = get_default_section_parser()
    return parser.parse_image(image_input, language=language)


def parse_section_from_pdf(
    pdf_path: str,
    page_number: int,
    bbox: Union[BoundingBox, dict[str, float], tuple[float, float, float, float], list[float]],
    language: str = "en",
    scale: float = 2.0
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
