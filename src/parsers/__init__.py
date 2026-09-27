"""
src/parsers package re-exports
"""
from src.parsers.docling_parser import DoclingParser
from src.parsers.pypdfium_parser import PyPdfiumParser
from src.parsers.section_ocr import (
    OCRLine,
    OCRResult,
    SectionOCRParser,
    crop_pdf_region,
    get_default_section_parser,
    normalize_bbox_coords,
    normalize_to_pil,
    parse_image_ocr,
    parse_section_from_pdf,
    set_default_section_parser,
)
from src.parsers.pdf_utils import open_pdf

__all__ = [
    "DoclingParser",
    "PyPdfiumParser",
    "SectionOCRParser",
    "OCRLine",
    "OCRResult",
    "crop_pdf_region",
    "get_default_section_parser",
    "normalize_bbox_coords",
    "normalize_to_pil",
    "parse_image_ocr",
    "parse_section_from_pdf",
    "set_default_section_parser",
    "open_pdf",
]
