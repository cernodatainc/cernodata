"""
src/dom/enums.py

Enumerations for DOM element types, extraction presets, and pipeline actions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union


class DOMNodeType(str, Enum):
    """Normalized structural types for DocumentDOM nodes."""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TABLE_GRID = "table_grid"
    FIGURE = "figure"
    HEADER_FOOTER = "header_footer"
    PAGE_HEADER = "page_header"
    FOOTER = "footer"
    LIST_ITEM = "list_item"
    CAPTION = "caption"
    CODE_BLOCK = "code_block"
    MULTI_COLUMN_GROUP = "multi_column_group"
    TEXT = "text"

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def coerce(cls, value: Union[DOMNodeType, Any]) -> DOMNodeType:
        """Coerces a raw type value into a valid DOMNodeType member."""
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.PARAGRAPH
        raw = str(value.value if isinstance(value, Enum) else value).strip().lower()
        if not raw:
            return cls.PARAGRAPH
        try:
            return cls(raw)
        except ValueError:
            return cls.PARAGRAPH


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

    @classmethod
    def coerce(cls, value: Union[PipelineAction, Any]) -> PipelineAction:
        """Coerces a raw action value into a valid PipelineAction member."""
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.ACCEPT_OUTPUT
        raw = str(value.value if isinstance(value, Enum) else value).strip().upper()
        if not raw:
            return cls.ACCEPT_OUTPUT
        return cls(raw)


class DOMNodeOrigin(str, Enum):
    """Provenance classification for DocumentDOM nodes."""

    PARSED = "parsed"
    POSTPROCESSED = "postprocessed"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def coerce(cls, value: Optional[Union[DOMNodeOrigin, Any]]) -> Optional[DOMNodeOrigin]:
        """Coerces an optional origin value into a DOMNodeOrigin member or None."""
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        raw = str(value.value if isinstance(value, Enum) else value).strip().lower()
        if not raw:
            return None
        return cls(raw)


class DecisionStatus(str, Enum):
    """Evaluation status outcomes for pipeline quality decisions."""

    ACCEPT = "ACCEPT"
    TRIGGER_FALLBACK = "TRIGGER_FALLBACK"
    REJECT = "REJECT"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def coerce(cls, value: Union[DecisionStatus, Any]) -> DecisionStatus:
        """Coerces a raw status value into a valid DecisionStatus member."""
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.UNKNOWN
        raw = str(value.value if isinstance(value, Enum) else value).strip().upper()
        if not raw:
            return cls.UNKNOWN
        return cls(raw)


class ViolationSeverity(str, Enum):
    """Severity levels for quality violation records."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    WARNING = "WARNING"
    INFO = "INFO"
    ERROR = "ERROR"

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def coerce(cls, value: Union[ViolationSeverity, Any]) -> ViolationSeverity:
        """Coerces a raw severity value into a valid ViolationSeverity member."""
        if isinstance(value, cls):
            return value
        if value is None:
            return cls.MEDIUM
        raw = str(value.value if isinstance(value, Enum) else value).strip().upper()
        if not raw:
            return cls.MEDIUM
        return cls(raw)
