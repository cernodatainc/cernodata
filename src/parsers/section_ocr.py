"""
src/parsers/section_ocr.py

Targeted OCR parser for document sections, cutouts, and bounding box regions.
Uses RapidOCR with PyTorch CPU backend by default, with support for base64 cutouts,
PDF crops, and extensible custom OCR engine backends.
"""

from __future__ import annotations

import inspect
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image

logger = logging.getLogger("cernodata.parsers.section_ocr")

from src.dom.bounding_box import BoundingBox
from src.parsers.ocr_imaging import crop_pdf_region, normalize_to_pil
from src.parsers.ocr_models import OCRLine, OCRResult, create_ocr_result, normalize_bbox_coords

HAS_RAPIDOCR = False
try:
    from rapidocr import EngineType, RapidOCR

    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False


class SectionOCRParser:
    """Targeted OCR parser for document sections, cutouts, and bounding boxes supporting multiple engines."""

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
        self._engine_registry: Dict[str, Any] = {}
        if engine is not None:
            self._engine_registry["rapidocr"] = engine
        elif engine_factory is not None:
            self._engine_registry["rapidocr"] = engine_factory

    def register_engine(self, name: str, engine_or_factory: Any) -> None:
        """Registers a custom OCR engine instance or factory by name."""
        self._engine_registry[name.lower().strip()] = engine_or_factory

    def get_available_engines(self) -> List[str]:
        """Returns list of all available and registered OCR engine names."""
        known = ["rapidocr", "tesseract", "easyocr"]
        for k in self._engine_registry.keys():
            if k not in known:
                known.append(k)
        return known

    def _create_tesseract_engine(self) -> Optional[Any]:
        """Creates Tesseract OCR engine wrapper if pytesseract is installed."""
        try:
            import pytesseract
            return lambda arr: pytesseract.image_to_string(arr, lang=self.language or "eng")
        except Exception as ex:
            logger.debug("Tesseract engine initialization unavailable: %s", ex)
            return None

    def _create_easyocr_engine(self) -> Optional[Any]:
        """Creates EasyOCR engine wrapper if easyocr is installed."""
        try:
            import easyocr
            langs = [self.language] if self.language else ["en"]
            reader = easyocr.Reader(langs)
            return lambda arr: reader.readtext(arr)
        except Exception as ex:
            logger.debug("EasyOCR engine initialization unavailable: %s", ex)
            return None

    def _resolve_engine_entry(self, entry: Any) -> Any:
        if callable(entry):
            try:
                sig = inspect.signature(entry)
                req = [
                    p for p in sig.parameters.values()
                    if p.default == inspect.Parameter.empty
                    and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                ]
                if len(req) == 0:
                    return entry()
            except (ValueError, TypeError) as ex:
                logger.debug("Signature inspection skipped: %s", ex)
        return entry

    def _get_engine_by_name(self, name: str) -> Optional[Any]:
        """Resolves an OCR engine instance or callable by its identifier."""
        norm_name = name.lower().strip()
        if norm_name in self._engine_registry:
            return self._resolve_engine_entry(self._engine_registry[norm_name])
        if norm_name == "rapidocr":
            return self._get_engine()
        if norm_name == "tesseract":
            return self._create_tesseract_engine()
        if norm_name == "easyocr":
            return self._create_easyocr_engine()
        return None

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
                params={"Det.engine_type": EngineType.TORCH, "Cls.engine_type": EngineType.TORCH, "Rec.engine_type": EngineType.TORCH}
            )
        except Exception as ex:
            logger.warning("RapidOCR torch engine initialization failed: %s", ex)
            try:
                return RapidOCR()
            except Exception as fallback_ex:
                logger.warning("RapidOCR default engine initialization failed: %s", fallback_ex, exc_info=True)
                return None

    def _create_cli_subprocess_engine(self) -> Optional[Any]:
        return None

    def _create_http_endpoint_engine(self) -> Optional[Any]:
        return None

    def _create_engine(self) -> Optional[Any]:
        """Creates engine using registered engine_factory or fallback default."""
        if self._engine_factory is not None:
            try:
                return self._engine_factory()
            except Exception as ex:
                logger.warning("Custom OCR engine factory failed: %s", ex, exc_info=True)
                return None
        custom_engine = self._create_cli_subprocess_engine() or self._create_http_endpoint_engine()
        if custom_engine is not None:
            return custom_engine
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

        if isinstance(result, str):
            clean = result.strip()
            str_lines: List[OCRLine] = [
                {"text": ln, "confidence": 1.0, "bbox": None}
                for ln in clean.splitlines() if ln.strip()
            ]
            return clean, 1.0, str_lines

        if isinstance(result, dict) and "text" in result and "txts" not in result:
            clean_dict_text = str(result.get("text", "")).strip()
            dict_conf = float(result.get("confidence", 1.0))
            raw_dict_lines = result.get("lines")
            parsed_dict_lines: List[OCRLine] = (
                list(raw_dict_lines)
                if isinstance(raw_dict_lines, list)
                else [{"text": ln, "confidence": dict_conf, "bbox": None} for ln in clean_dict_text.splitlines() if ln.strip()]
            )
            return clean_dict_text, dict_conf, parsed_dict_lines

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
                except Exception as ex:
                    logger.debug("Skipping malformed OCR box for line %d: %s", i, ex)
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
        engine_name: Optional[str] = None,
    ) -> OCRResult:
        """Parses an image containing a document section using a targeted OCR engine."""
        try:
            pil_img = normalize_to_pil(image_input)
        except TypeError as ex:
            return create_ocr_result(success=False, error=str(ex))
        except Exception as ex:
            logger.warning("Failed to load OCR input image: %s", ex, exc_info=True)
            return create_ocr_result(success=False, error=f"Failed to load image: {str(ex)}")

        if pil_img.width <= 0 or pil_img.height <= 0:
            return create_ocr_result(success=False, error="Image is empty or has invalid dimensions.")

        target_engine_name = (engine_name or "rapidocr").lower().strip()
        engine = self._get_engine_by_name(target_engine_name)
        if engine is None:
            err_msg = "OCR engine not available." if target_engine_name == "rapidocr" else f"OCR engine '{target_engine_name}' not available."
            return create_ocr_result(success=False, error=err_msg)

        try:
            result = self._run_engine(engine, pil_img)
        except Exception as ex:
            logger.warning("OCR inference error for engine '%s': %s", target_engine_name, ex, exc_info=True)
            return create_ocr_result(success=False, error=f"OCR inference error: {str(ex)}")

        joined_text, avg_confidence, lines = self._parse_engine_result(result)
        return create_ocr_result(success=True, text=joined_text, confidence=avg_confidence, lines=lines)

    def parse_image_multi(
        self,
        image_input: Union[Image.Image, bytes, bytearray, str, os.PathLike[str], np.ndarray],
        engines: Optional[Sequence[str]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, OCRResult]:
        """Executes multiple OCR engines against an image and returns results mapped by engine name."""
        engine_list = [str(e).strip().lower() for e in engines] if engines else ["rapidocr"]
        return {eng: self.parse_image(image_input, language=language, engine_name=eng) for eng in engine_list}

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
        engine_name: Optional[str] = None,
    ) -> OCRResult:
        """Extracts and crops a specific section bounding box from a PDF page and runs OCR."""
        try:
            cropped_img = self.crop_section_image(pdf_path, page_number, bbox, scale=scale)
        except (FileNotFoundError, ValueError, IndexError, RuntimeError) as ex:
            return create_ocr_result(success=False, error=str(ex))
        except Exception as ex:
            logger.warning("Failed to crop PDF section: %s", ex, exc_info=True)
            return create_ocr_result(success=False, error=f"Failed to crop PDF section: {str(ex)}")

        return self.parse_image(cropped_img, language=language, engine_name=engine_name)

    def parse_section_from_pdf_multi(
        self,
        pdf_path: str,
        page_number: int,
        bbox: Union[BoundingBox, dict[str, float], Tuple[float, float, float, float], Sequence[float]],
        engines: Optional[Sequence[str]] = None,
        language: Optional[str] = None,
        scale: float = 2.0,
    ) -> Dict[str, OCRResult]:
        """Crops a section from a PDF page once and processes it with multiple OCR engines."""
        try:
            cropped_img = self.crop_section_image(pdf_path, page_number, bbox, scale=scale)
        except (FileNotFoundError, ValueError, IndexError, RuntimeError) as ex:
            err_res = create_ocr_result(success=False, error=str(ex))
            engine_list = [str(e).strip().lower() for e in engines] if engines else ["rapidocr"]
            return {eng: err_res for eng in engine_list}
        except Exception as ex:
            logger.warning("Failed to crop PDF section: %s", ex, exc_info=True)
            err_res = create_ocr_result(success=False, error=f"Failed to crop PDF section: {str(ex)}")
            engine_list = [str(e).strip().lower() for e in engines] if engines else ["rapidocr"]
            return {eng: err_res for eng in engine_list}

        return self.parse_image_multi(cropped_img, engines=engines, language=language)

    def process_dom_node(
        self,
        node: Any,
        pdf_path: Optional[str] = None,
        image_input: Optional[Any] = None,
        engines: Optional[Sequence[str]] = None,
        language: Optional[str] = None,
        prompt_accept: Optional[Callable[[str, str, float], bool]] = None,
        interactive: bool = False,
    ) -> Dict[str, Any]:
        """Processes a DOM node bounding box across one or more OCR engines and prompts for acceptance."""
        if image_input is not None:
            results = self.parse_image_multi(image_input, engines=engines, language=language)
        elif pdf_path:
            results = self.parse_section_from_pdf_multi(
                pdf_path,
                getattr(node, "global_page_index", 1),
                getattr(node, "bounding_box", (0.0, 0.0, 0.0, 0.0)),
                engines=engines,
                language=language,
            )
        else:
            return {"results": {}, "accepted": False, "error": "Either image_input or pdf_path must be provided."}

        for eng_name, res in results.items():
            if not res.get("success"):
                continue
            text, conf = res.get("text", ""), float(res.get("confidence", 0.0))
            is_accepted = False
            if prompt_accept is not None:
                is_accepted = prompt_accept(eng_name, text, conf)
            elif interactive:
                prompt_msg = f"Accept OCR output from '{eng_name}' for node '{getattr(node, 'node_id', '')}'? [y/N]: "
                is_accepted = input(prompt_msg).strip().lower() in ("y", "yes")

            if is_accepted:
                if hasattr(node, "content") and isinstance(node.content, dict):
                    node.content["raw_text"] = text
                if hasattr(node, "user_correction_note"):
                    node.user_correction_note = text
                if hasattr(node, "ocr_confidence"):
                    node.ocr_confidence = conf
                if hasattr(node, "is_incorrect_text"):
                    node.is_incorrect_text = False
                return {
                    "results": results,
                    "accepted": True,
                    "accepted_engine": eng_name,
                    "accepted_text": text,
                    "accepted_confidence": conf,
                }

        return {"results": results, "accepted": False, "accepted_engine": None, "accepted_text": None, "accepted_confidence": None}


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
    engine_name: Optional[str] = None,
) -> OCRResult:
    """Module-level convenience function for targeted image OCR."""
    parser = get_default_section_parser()
    return parser.parse_image(image_input, language=language, engine_name=engine_name)


def parse_image_ocr_multi(
    image_input: Union[Image.Image, bytes, bytearray, str, os.PathLike[str], np.ndarray],
    engines: Optional[Sequence[str]] = None,
    language: str = "en",
) -> Dict[str, OCRResult]:
    """Module-level convenience function for targeted multi-engine image OCR."""
    return get_default_section_parser().parse_image_multi(image_input, engines=engines, language=language)


def parse_section_from_pdf(
    pdf_path: str,
    page_number: int,
    bbox: Union[BoundingBox, dict[str, float], Tuple[float, float, float, float], Sequence[float]],
    language: str = "en",
    scale: float = 2.0,
    engine_name: Optional[str] = None,
) -> OCRResult:
    """Module-level convenience function for cropping a section from a PDF and running OCR."""
    return get_default_section_parser().parse_section_from_pdf(
        pdf_path, page_number, bbox, language=language, scale=scale, engine_name=engine_name
    )


def parse_section_from_pdf_multi(
    pdf_path: str,
    page_number: int,
    bbox: Union[BoundingBox, dict[str, float], Tuple[float, float, float, float], Sequence[float]],
    engines: Optional[Sequence[str]] = None,
    language: str = "en",
    scale: float = 2.0,
) -> Dict[str, OCRResult]:
    """Module-level convenience function for cropping a section from a PDF and running multiple OCR engines."""
    return get_default_section_parser().parse_section_from_pdf_multi(
        pdf_path, page_number, bbox, engines=engines, language=language, scale=scale
    )


def get_available_ocr_engines() -> List[str]:
    """Returns list of available and registered OCR engine names."""
    return get_default_section_parser().get_available_engines()


__all__ = [
    "OCRLine",
    "OCRResult",
    "SectionOCRParser",
    "create_ocr_result",
    "crop_pdf_region",
    "get_available_ocr_engines",
    "get_default_section_parser",
    "normalize_bbox_coords",
    "normalize_to_pil",
    "parse_image_ocr",
    "parse_image_ocr_multi",
    "parse_section_from_pdf",
    "parse_section_from_pdf_multi",
    "set_default_section_parser",
]
