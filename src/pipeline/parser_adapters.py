"""
src/pipeline/parser_adapters.py

Preset-specific parser adapters and options normalization for document ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from src.dom import DocumentDOM
from src.parsers import DoclingParser, PyPdfiumParser
from src.pipeline.planner_models import IngestionConfig


@dataclass(frozen=True)
class ParserExecutionOptions:
    """Normalized options container for parser engine execution."""
    language: Optional[str] = "en"
    preset: str = "docling_fast"
    ocr_engine: str = "auto"
    ocr_scale: Optional[float] = None
    force_full_page_ocr: bool = False
    do_table_structure: bool = True

    @classmethod
    def from_inputs(
        cls,
        language: Optional[str] = "en",
        preset: str = "docling_fast",
        ocr_engine: str = "auto",
        ocr_scale: Optional[float] = None,
        force_full_page_ocr: bool = False,
        do_table_structure: bool = True,
        config: Optional[IngestionConfig] = None,
    ) -> ParserExecutionOptions:
        """Constructs normalized execution options prioritizing explicit config if provided."""
        if config is not None:
            return cls(
                language=config.language,
                preset=config.preset,
                ocr_engine=ocr_engine,
                ocr_scale=config.ocr_scale if config.ocr_scale is not None else ocr_scale,
                force_full_page_ocr=config.force_full_page_ocr,
                do_table_structure=config.do_table_structure,
            )
        return cls(
            language=language,
            preset=preset,
            ocr_engine=ocr_engine,
            ocr_scale=ocr_scale,
            force_full_page_ocr=force_full_page_ocr,
            do_table_structure=do_table_structure,
        )


@runtime_checkable
class ParserPresetAdapter(Protocol):
    """Protocol defining the interface for parser preset execution adapters."""

    def can_handle(self, preset: str) -> bool:
        """Determines if this adapter supports the given preset identifier."""
        ...

    def parse(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM:
        """Executes parsing on the target PDF path using normalized options."""
        ...


class PyPdfiumPresetAdapter:
    """Adapter executing the pypdfium_rapidocr standalone parser preset."""

    SUPPORTED_PRESETS = frozenset({"pypdfium_rapidocr"})

    def can_handle(self, preset: str) -> bool:
        return preset in self.SUPPORTED_PRESETS

    def parse(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM:
        scale = options.ocr_scale if options.ocr_scale is not None else 2.0
        return PyPdfiumParser(language=options.language, scale=scale).parse(resolved_path)


class DoclingPresetAdapter:
    """Adapter executing Docling layout and OCR parser presets."""

    def can_handle(self, preset: str) -> bool:
        # Default fallback adapter handling all docling presets
        return True

    def parse(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM:
        return DoclingParser(
            language=options.language,
            preset=options.preset,
            ocr_engine=options.ocr_engine,
            ocr_scale=options.ocr_scale,
            force_full_page_ocr=options.force_full_page_ocr,
            do_table_structure=options.do_table_structure,
        ).parse(resolved_path)
