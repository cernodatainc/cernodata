"""
src/dom/enums.py

Enumerations for DOM element types, extraction presets, and pipeline actions.
"""

from enum import Enum


class DOMNodeType(str, Enum):
    """Normalized structural types for DocumentDOM nodes."""
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE_GRID = "table_grid"
    FIGURE = "figure"
    HEADER_FOOTER = "header_footer"
    MULTI_COLUMN_GROUP = "multi_column_group"
    TEXT = "text"

    def __str__(self) -> str:
        return str(self.value)


class PresetKind(str, Enum):
    """Identifiers for available document extraction presets."""
    DOCLING_FAST = "docling_fast"
    DOCLING_DEEP = "docling_deep"
    PYPDFIUM_RAPIDOCR = "pypdfium_rapidocr"
    VISION_LLM_DIRECT = "vision_llm_direct"

    def __str__(self) -> str:
        return str(self.value)


class PipelineAction(str, Enum):
    """Decision tree outcome actions."""
    ACCEPT_OUTPUT = "ACCEPT_OUTPUT"
    ACCEPT_PARSE = "ACCEPT_PARSE"
    PATH_A_SWITCH_PRESET = "PATH_A_SWITCH_PRESET"
    PATH_B_WIGGLE_PARAMETERS = "PATH_B_WIGGLE_PARAMETERS"

    def __str__(self) -> str:
        return str(self.value)
