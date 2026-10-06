"""
src/pipeline/parser_dispatch.py

Document parser resolution and dispatching for document ingestion presets.
"""

import os
from typing import Optional

from src.dom import DocumentDOM
from src.parsers import DoclingParser, PyPdfiumParser
from src.pipeline.planner_models import IngestionConfig
from src.utils import resolve_pdf_path


class DocumentParserDispatcher:
    """Dispatches document parsing requests to the appropriate parser engine."""

    def parse(
        self,
        pdf_path: str,
        language: Optional[str] = "en",
        preset: str = "docling_fast",
        ocr_engine: str = "auto",
        ocr_scale: Optional[float] = None,
        force_full_page_ocr: bool = False,
        do_table_structure: bool = True,
        config: Optional[IngestionConfig] = None,
    ) -> DocumentDOM:
        """Parses PDF document using the specified preset into DocumentDOM IR."""
        if config is not None:
            language = config.language
            preset = config.preset
            ocr_scale = config.ocr_scale if config.ocr_scale is not None else ocr_scale
            force_full_page_ocr = config.force_full_page_ocr
            do_table_structure = config.do_table_structure

        resolved_path = resolve_pdf_path(pdf_path)
        if not os.path.exists(resolved_path):
            raise FileNotFoundError(f"PDF document not found: '{pdf_path}'")

        if preset == "pypdfium_rapidocr":
            scale = ocr_scale if ocr_scale is not None else 2.0
            return PyPdfiumParser(language=language, scale=scale).parse(resolved_path)

        return DoclingParser(
            language=language,
            preset=preset,
            ocr_engine=ocr_engine,
            ocr_scale=ocr_scale,
            force_full_page_ocr=force_full_page_ocr,
            do_table_structure=do_table_structure,
        ).parse(resolved_path)


_default_dispatcher = DocumentParserDispatcher()


def parse_document(
    pdf_path: str,
    language: Optional[str] = "en",
    preset: str = "docling_fast",
    ocr_engine: str = "auto",
    ocr_scale: Optional[float] = None,
    force_full_page_ocr: bool = False,
    do_table_structure: bool = True,
    config: Optional[IngestionConfig] = None,
) -> DocumentDOM:
    """Module-level dispatch function parsing PDF document using the specified preset."""
    return _default_dispatcher.parse(
        pdf_path=pdf_path,
        language=language,
        preset=preset,
        ocr_engine=ocr_engine,
        ocr_scale=ocr_scale,
        force_full_page_ocr=force_full_page_ocr,
        do_table_structure=do_table_structure,
        config=config,
    )
