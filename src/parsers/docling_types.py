"""
src/parsers/docling_types.py

Structural typing protocols for Docling document, provenance, bounding box,
item, and table interfaces to avoid pervasive Any and reflection.
"""

from __future__ import annotations

from typing import List, Mapping, Optional, Protocol, Sequence, Union, runtime_checkable


@runtime_checkable
class DoclingBBox(Protocol):
    """Minimal bounding box coordinates protocol."""

    l: float
    t: float
    r: float
    b: float


@runtime_checkable
class DoclingBBoxWithOrigin(DoclingBBox, Protocol):
    """Bounding box carrying a coordinate origin indicator."""

    coord_origin: object


@runtime_checkable
class DoclingBBoxConvertible(DoclingBBox, Protocol):
    """Bounding box supporting conversion to top-left origin."""

    def to_top_left_origin(self, page_height: float) -> DoclingBBox:
        ...


@runtime_checkable
class DoclingPageSize(Protocol):
    """Page size metadata exposing page height in points."""

    @property
    def height(self) -> float:
        ...


@runtime_checkable
class DoclingPage(Protocol):
    """Docling page entry exposing optional page size."""

    @property
    def size(self) -> Optional[DoclingPageSize]:
        ...


@runtime_checkable
class DoclingDocument(Protocol):
    """Docling document exposing indexed or sequential page metadata."""

    @property
    def pages(self) -> Union[Mapping[int, DoclingPage], Sequence[DoclingPage]]:
        ...


@runtime_checkable
class DoclingProvenance(Protocol):
    """Provenance record linking an item to a page number and bounding box."""

    page_no: int
    bbox: Optional[DoclingBBox]


@runtime_checkable
class ProvenanceBearing(Protocol):
    """Item exposing a sequence of provenance records."""

    prov: Sequence[DoclingProvenance]


@runtime_checkable
class AngleBearing(Protocol):
    """Object exposing an optional rotation angle."""

    angle: Optional[float]


@runtime_checkable
class EnumLikeLabel(Protocol):
    """Enum-like label object exposing a string value."""

    value: str


@runtime_checkable
class LabeledItem(Protocol):
    """Item exposing a label string or enum-like label."""

    label: Union[str, EnumLikeLabel, None]


@runtime_checkable
class TextItem(Protocol):
    """Item exposing an optional text attribute."""

    text: Optional[str]


@runtime_checkable
class CaptionableItem(Protocol):
    """Figure or media item supporting caption lookup against a document."""

    def caption_text(self, doc: object) -> Optional[str]:
        ...


@runtime_checkable
class ConfidenceBearing(Protocol):
    """Object exposing an optional numeric confidence score."""

    confidence: Optional[float]


@runtime_checkable
class DocTextCell(Protocol):
    """Table cell supporting document-aware text extraction."""

    def _get_text(self, doc: object = None) -> str:
        ...


@runtime_checkable
class HeaderCell(Protocol):
    """Table cell indicating whether it belongs to a column header."""

    column_header: bool


@runtime_checkable
class SpanningCell(Protocol):
    """Table cell exposing row and column span counts."""

    row_span: int
    col_span: int


@runtime_checkable
class BBoxBearing(Protocol):
    """Object exposing an optional Docling bounding box."""

    bbox: Optional[DoclingBBox]


@runtime_checkable
class DoclingTableData(Protocol):
    """Structured table grid metadata from a Docling TableItem."""

    num_rows: int
    num_cols: int
    grid: Sequence[Sequence[object]]


@runtime_checkable
class DoclingTableItem(Protocol):
    """Docling table item exposing structured table data."""

    data: Optional[DoclingTableData]


@runtime_checkable
class MarkdownExportable(Protocol):
    """Item supporting Markdown export."""

    def export_to_markdown(self, doc: object = None) -> str:
        ...


@runtime_checkable
class OcrLangConfigurable(Protocol):
    """OCR options object supporting language list configuration."""

    lang: List[str]


@runtime_checkable
class OcrScaleConfigurable(Protocol):
    """OCR options object supporting scale factor configuration."""

    scale: float


@runtime_checkable
class OcrModeConfigurable(Protocol):
    """OCR options object supporting OCR mode configuration."""

    mode: object
