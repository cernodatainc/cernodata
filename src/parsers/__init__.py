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
    get_available_ocr_engines,
    get_default_section_parser,
    normalize_bbox_coords,
    normalize_to_pil,
    parse_image_ocr,
    parse_image_ocr_multi,
    parse_section_from_pdf,
    parse_section_from_pdf_multi,
    set_default_section_parser,
)
from src.parsers.pdf_utils import open_pdf
from src.parsers.table_parser import (
    ParsedTable,
    ParsedTableCell,
    TableParser,
    compute_table_alignment_score,
    extract_table_headers_and_title,
    generate_html_table,
    generate_markdown_table,
    parse_docling_table,
    parse_markdown_table,
    parse_table_content,
)

__all__ = [
    "DoclingParser",
    "PyPdfiumParser",
    "SectionOCRParser",
    "OCRLine",
    "OCRResult",
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
    "open_pdf",
    "ParsedTable",
    "ParsedTableCell",
    "TableParser",
    "compute_table_alignment_score",
    "extract_table_headers_and_title",
    "generate_html_table",
    "generate_markdown_table",
    "parse_docling_table",
    "parse_markdown_table",
    "parse_table_content",
]
