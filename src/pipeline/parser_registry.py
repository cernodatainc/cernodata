"""
src/pipeline/parser_registry.py

Backwards-compatibility shim forwarding to src.pipeline.parsers.registry.
"""

from __future__ import annotations

from src.pipeline.parsers.registry import (
    ParserPresetRegistry,
    get_default_parser_registry,
)

__all__ = [
    "ParserPresetRegistry",
    "get_default_parser_registry",
]
