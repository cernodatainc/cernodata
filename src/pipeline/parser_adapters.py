"""
src/pipeline/parser_adapters.py

Backwards-compatibility shim forwarding to src.pipeline.parsers.adapters.
"""

from __future__ import annotations

from src.pipeline.parsers.adapters import (
    DoclingPresetAdapter,
    ParserExecutionOptions,
    ParserPresetAdapter,
    PyPdfiumPresetAdapter,
)

__all__ = [
    "DoclingPresetAdapter",
    "ParserExecutionOptions",
    "ParserPresetAdapter",
    "PyPdfiumPresetAdapter",
]
