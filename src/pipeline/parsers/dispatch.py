"""
src/pipeline/parsers/dispatch.py

Document parser resolution and dispatching for document ingestion presets.
"""

from __future__ import annotations

import os
from typing import Optional

from src.dom import DocumentDOM
from src.pipeline.parsers.adapters import (
    DoclingPresetAdapter,
    ParserExecutionOptions,
    ParserPresetAdapter,
    PyPdfiumPresetAdapter,
)
from src.pipeline.parsers.registry import (
    ParserPresetRegistry,
    get_default_parser_registry,
)
from src.pipeline.planner.models import IngestionConfig
from src.utils import resolve_pdf_path

__all__ = [
    "DoclingPresetAdapter",
    "DocumentParserDispatcher",
    "ParserExecutionOptions",
    "ParserPresetAdapter",
    "ParserPresetRegistry",
    "PyPdfiumPresetAdapter",
    "get_default_parser_registry",
    "parse_document",
]


class DocumentParserDispatcher:
    """Dispatches document parsing requests through the configured parser preset registry."""

    def __init__(self, registry: Optional[ParserPresetRegistry] = None) -> None:
        self._registry = registry or get_default_parser_registry()

    @property
    def registry(self) -> ParserPresetRegistry:
        return self._registry

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
        options = ParserExecutionOptions.from_inputs(
            language=language,
            preset=preset,
            ocr_engine=ocr_engine,
            ocr_scale=ocr_scale,
            force_full_page_ocr=force_full_page_ocr,
            do_table_structure=do_table_structure,
            config=config,
        )

        resolved_path = resolve_pdf_path(pdf_path)
        if not os.path.exists(resolved_path):
            raise FileNotFoundError(f"PDF document not found: '{pdf_path}'")

        return self._registry.execute(resolved_path, options)


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
