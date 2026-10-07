"""
src/pipeline/parsers/__init__.py

Pipeline parser dispatching, preset adapters, and extensible parser registry.
"""

from __future__ import annotations

from src.pipeline.parsers.adapters import (
    DoclingPresetAdapter,
    ParserExecutionOptions,
    ParserPresetAdapter,
    PyPdfiumPresetAdapter,
)
from src.pipeline.parsers.dispatch import (
    DocumentParserDispatcher,
    parse_document,
)
from src.pipeline.parsers.registry import (
    ParserPresetRegistry,
    get_default_parser_registry,
)

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
