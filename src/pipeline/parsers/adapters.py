"""
src/pipeline/parsers/adapters.py

Preset-specific parser adapters and options normalization for document ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from src.dom import DocumentDOM
from src.parsers import DoclingParser, PyPdfiumParser
from src.pipeline.planner.models import IngestionConfig

DEFAULT_PYPDFIUM_SCALE: float = 2.0
DEFAULT_OCR_ENGINE: str = "auto"


@dataclass(frozen=True)
class ParserExecutionOptions:
    """Normalized options container for parser engine execution."""

    preset: str
    language: Optional[str] = "en"
    ocr_engine: str = DEFAULT_OCR_ENGINE
    ocr_scale: Optional[float] = None
    force_full_page_ocr: bool = False
    do_table_structure: bool = True
    extra_parameters: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_inputs(
        cls,
        language: Optional[str] = "en",
        preset: Optional[str] = None,
        ocr_engine: str = DEFAULT_OCR_ENGINE,
        ocr_scale: Optional[float] = None,
        force_full_page_ocr: bool = False,
        do_table_structure: bool = True,
        config: Optional[IngestionConfig] = None,
        extra_parameters: Optional[Dict[str, Any]] = None,
    ) -> ParserExecutionOptions:
        """Constructs normalized execution options prioritizing explicit config if provided."""
        merged_extra: Dict[str, Any] = {}
        if config is not None:
            cfg_extra = config.get_option("extra_parameters")
            if isinstance(cfg_extra, dict):
                merged_extra.update(cfg_extra)
            cfg_wiggle = config.get_option("wiggle_parameters")
            if isinstance(cfg_wiggle, dict):
                merged_extra.update(cfg_wiggle)
        if extra_parameters:
            merged_extra.update(extra_parameters)

        if config is not None:
            resolved_lang = config.language
            resolved_preset = config.preset
            resolved_scale = config.ocr_scale if config.ocr_scale is not None else ocr_scale
            resolved_full_page = config.force_full_page_ocr
            resolved_tables = config.do_table_structure
            return cls(
                language=resolved_lang,
                preset=resolved_preset,
                ocr_engine=ocr_engine,
                ocr_scale=resolved_scale,
                force_full_page_ocr=resolved_full_page,
                do_table_structure=resolved_tables,
                extra_parameters=merged_extra,
            )

        if not preset:
            raise ValueError("A parser preset or IngestionConfig must be provided.")

        return cls(
            language=language,
            preset=preset,
            ocr_engine=ocr_engine,
            ocr_scale=ocr_scale,
            force_full_page_ocr=force_full_page_ocr,
            do_table_structure=do_table_structure,
            extra_parameters=merged_extra,
        )


@runtime_checkable
class ParserPresetAdapter(Protocol):
    """Protocol defining the interface for parser preset execution adapters."""

    @property
    def preset_id(self) -> Optional[str]:
        """Static preset identifier when bound to a single custom preset."""
        ...

    def can_handle(self, preset: str) -> bool:
        """Determines if this adapter supports the given preset identifier."""
        ...

    def parse(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM:
        """Executes parsing on the target PDF path using normalized options."""
        ...


class PyPdfiumPresetAdapter:
    """Adapter executing the pypdfium_rapidocr standalone parser preset."""

    preset_id: Optional[str] = "pypdfium_rapidocr"
    SUPPORTED_PRESETS = frozenset({"pypdfium_rapidocr"})

    def can_handle(self, preset: str) -> bool:
        return preset in self.SUPPORTED_PRESETS

    def parse(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM:
        scale = options.ocr_scale if options.ocr_scale is not None else DEFAULT_PYPDFIUM_SCALE
        return PyPdfiumParser(language=options.language, scale=scale).parse(resolved_path)


class DoclingPresetAdapter:
    """Adapter executing Docling layout and OCR parser presets."""

    preset_id: Optional[str] = None
    SUPPORTED_PRESETS = frozenset({"docling_fast", "docling_deep"})

    def can_handle(self, preset: str) -> bool:
        return preset in self.SUPPORTED_PRESETS or preset.startswith("docling_")

    def parse(self, resolved_path: str, options: ParserExecutionOptions) -> DocumentDOM:
        return DoclingParser(
            language=options.language,
            preset=options.preset,
            ocr_engine=options.ocr_engine,
            ocr_scale=options.ocr_scale,
            force_full_page_ocr=options.force_full_page_ocr,
            do_table_structure=options.do_table_structure,
        ).parse(resolved_path)
