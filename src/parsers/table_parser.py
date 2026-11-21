"""
src/parsers/table_parser.py

Table content parser with row and column awareness.
Extracts rows, columns, headers, cell coordinates, alignment scores,
and structural grids from Docling TableItem objects and Markdown tables.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.parsers.docling_types import (
    BBoxBearing,
    ConfidenceBearing,
    DoclingTableItem,
    DocTextCell,
    HeaderCell,
    MarkdownExportable,
    SpanningCell,
    TextItem,
)

logger = logging.getLogger("cernodata.parsers.table_parser")

DEFAULT_TABLE_MIN_ALIGNMENT_SCORE: float = 0.10
DEFAULT_TABLE_RAGGED_MULTIPLIER: float = 2.0


@dataclass
class ParsedTableCell:
    """Structured representation of an individual table cell with row and column indices."""

    row_idx: int
    col_idx: int
    text: str
    row_span: int = 1
    col_span: int = 1
    is_header: bool = False
    bbox: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes cell record into a dictionary."""
        record: Dict[str, Any] = {
            "row_idx": self.row_idx,
            "col_idx": self.col_idx,
            "text": self.text,
            "row_span": self.row_span,
            "col_span": self.col_span,
            "is_header": self.is_header,
        }
        if self.bbox is not None:
            record["bbox"] = dict(self.bbox)
        return record


@dataclass
class ParsedTable:
    """Comprehensive representation of a parsed table with row and column awareness."""

    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    columns: List[List[str]] = field(default_factory=list)
    num_rows: int = 0
    num_cols: int = 0
    cells: List[Dict[str, Any]] = field(default_factory=list)
    grid: List[List[Dict[str, Any]]] = field(default_factory=list)
    column_alignments: List[str] = field(default_factory=list)
    markdown_table: str = ""
    title: str = ""
    cell_alignment_score: float = 1.0
    is_consistent: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Exports parsed table state as a node content dictionary payload."""
        return {
            "headers": list(self.headers),
            "rows": [list(r) for r in self.rows],
            "columns": [list(c) for c in self.columns],
            "num_rows": self.num_rows,
            "num_cols": self.num_cols,
            "cells": [dict(c) for c in self.cells],
            "grid": [[dict(cell) for cell in row] for row in self.grid],
            "column_alignments": list(self.column_alignments),
            "markdown_table": self.markdown_table,
            "title": self.title,
            "cell_alignment_score": self.cell_alignment_score,
            "is_consistent": self.is_consistent,
        }

    @property
    def data_rows(self) -> List[List[str]]:
        """Returns data rows excluding the header row if headers were identified."""
        if self.headers and self.rows and self.rows[0] == self.headers:
            return self.rows[1:]
        return self.rows


def split_markdown_row(line: str) -> List[str]:
    """Splits a single markdown table row line into stripped cell text values."""
    trimmed = line.strip()
    if not trimmed:
        return []
    raw = re.split(r"(?<!\\)\|", trimmed)
    if raw and raw[0].strip() == "":
        raw = raw[1:]
    if raw and raw[-1].strip() == "":
        raw = raw[:-1]
    return [c.replace(r"\|", "|").strip() for c in raw]


def is_markdown_separator_row(cells: List[str]) -> bool:
    """Returns True if the list of cells represents a markdown delimiter row (e.g. :---:)."""
    return bool(cells) and all(bool(re.match(r"^:?-+:?$", c)) for c in cells)


def parse_column_alignments(separator_cells: List[str]) -> List[str]:
    """Extracts column alignment directives ('left', 'center', 'right', 'default') from separator cells."""
    alignments: List[str] = []
    for c in separator_cells:
        s = c.strip()
        if s.startswith(":") and s.endswith(":"):
            alignments.append("center")
        elif s.endswith(":"):
            alignments.append("right")
        elif s.startswith(":"):
            alignments.append("left")
        else:
            alignments.append("default")
    return alignments


def build_column_oriented_view(rows: List[List[str]], num_cols: int) -> List[List[str]]:
    """Constructs a column-oriented 2D list where columns[c] is the list of values in column c across all rows."""
    return [[r[c] if c < len(r) else "" for r in rows] for c in range(num_cols)]


def extract_table_headers_and_title(
    rows: List[List[str]],
    num_cols: int,
    grid_cells: Optional[Sequence[Sequence[object]]] = None,
) -> Tuple[List[str], List[List[str]], str]:
    """Extracts column headers, body rows, and optional table title banner from raw row data.

    Detects when row 0 is a spanning title or banner where all non-empty cells are identical
    or col_span spans the entire table, and promotes row 1 to true column headers.
    """
    if not rows:
        return [], [], ""
    if len(rows) == 1:
        return list(rows[0]), rows, ""
    r0 = rows[0]
    r0_clean = [c.strip() for c in r0 if c.strip()]
    is_spanning = False
    if num_cols > 1 and r0_clean and len(set(r0_clean)) == 1 and (len(r0) == num_cols or len(r0_clean) == num_cols):
        is_spanning = True
    elif num_cols > 1 and grid_cells and len(grid_cells) > 0 and len(grid_cells[0]) > 0:
        c0 = grid_cells[0][0]
        if isinstance(c0, SpanningCell) and int(c0.col_span or 1) >= num_cols and r0_clean:
            is_spanning = True
    if is_spanning and len(rows) > 1:
        title = r0_clean[0]
        r1_clean = [c.strip() for c in rows[1] if c.strip()]
        if len(set(r1_clean)) > 1:
            return list(rows[1]), rows[1:], title
    return list(rows[0]), rows, ""


def compute_table_alignment_score(
    rows: List[List[str]],
    expected_cols: Optional[int] = None,
    cell_confidences: Optional[List[float]] = None,
    preset: Optional[str] = None,
) -> float:
    """Computes a table cell alignment score based on row column-count raggedness and optional OCR cell confidences."""
    from src.quality.table_validator import compute_grid_consistency

    _ = (expected_cols, preset)
    grid_consistency = compute_grid_consistency([r for r in rows if isinstance(r, list)])

    if cell_confidences:
        avg_cell_conf = sum(cell_confidences) / len(cell_confidences)
        final_score = (grid_consistency + avg_cell_conf) / 2.0
    else:
        final_score = grid_consistency

    return round(final_score, 4)


def generate_markdown_table(
    headers: List[str],
    rows: List[List[str]],
    alignments: Optional[List[str]] = None,
) -> str:
    """Generates a formatted markdown table string from headers, data rows, and alignments."""
    if not headers and not rows:
        return ""
    all_rows = [headers] + rows if headers else rows
    max_cols = max(len(r) for r in all_rows)
    if max_cols == 0:
        return ""

    padded = [r + [""] * (max_cols - len(r)) for r in all_rows]
    col_widths = [max(3, max(len(str(padded[r][c])) for r in range(len(padded)))) for c in range(max_cols)]
    align = alignments or ["left"] * max_cols
    lines: List[str] = [
        "| " + " | ".join(padded[0][c].ljust(col_widths[c]) for c in range(max_cols)) + " |"
    ]
    sep: List[str] = []
    for c in range(max_cols):
        a = align[c] if c < len(align) else "left"
        w = col_widths[c]
        sep.append(":" + "-" * max(1, w - 2) + ":" if a == "center" else ("-" * max(1, w - 1) + ":" if a == "right" else "-" * w))
    lines.append("| " + " | ".join(sep) + " |")
    for r in range(1, len(padded)):
        lines.append("| " + " | ".join(padded[r][c].ljust(col_widths[c]) for c in range(max_cols)) + " |")
    return "\n".join(lines)


def generate_html_table(headers: List[str], rows: List[List[str]]) -> str:
    """Generates an HTML table string from headers and rows with escaped entities."""
    parts: List[str] = ['<table class="cernodata-table-grid">']
    if headers:
        th_tags = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
        parts.append(f"  <thead><tr>{th_tags}</tr></thead>")
    if rows:
        parts.append("  <tbody>")
        for r in rows:
            td_tags = "".join(f"<td>{html.escape(str(c))}</td>" for c in r)
            parts.append(f"    <tr>{td_tags}</tr>")
        parts.append("  </tbody>")
    parts.append("</table>")
    return "\n".join(parts)


def parse_markdown_table(
    markdown_text: str,
    preset: str = "docling_fast",
) -> ParsedTable:
    """Parses a markdown table string into a structured ParsedTable with row and column awareness."""
    lines = [ln.strip() for ln in markdown_text.strip().splitlines() if ln.strip()]
    table_lines = [ln for ln in lines if "|" in ln]
    if not table_lines:
        return ParsedTable(cell_alignment_score=0.0)

    raw_rows: List[List[str]] = []
    sep_idx: Optional[int] = None
    column_alignments: List[str] = []

    for idx, line in enumerate(table_lines):
        cells = split_markdown_row(line)
        if sep_idx is None and is_markdown_separator_row(cells):
            sep_idx = idx
            column_alignments = parse_column_alignments(cells)
            continue
        raw_rows.append(cells)

    if not raw_rows:
        return ParsedTable(cell_alignment_score=0.0)

    headers: List[str] = list(raw_rows[0]) if (sep_idx and sep_idx > 0) or len(raw_rows) > 1 else []
    max_cols = max((len(r) for r in raw_rows), default=0)
    if not column_alignments:
        column_alignments = ["default"] * max_cols

    columns = build_column_oriented_view(raw_rows, max_cols)
    cell_records: List[Dict[str, Any]] = []
    grid: List[List[Dict[str, Any]]] = []

    for r_idx, row_values in enumerate(raw_rows):
        grid_row: List[Dict[str, Any]] = []
        is_hdr = bool(headers and r_idx == 0)
        for c_idx in range(max_cols):
            val = row_values[c_idx] if c_idx < len(row_values) else ""
            c_dict = ParsedTableCell(row_idx=r_idx, col_idx=c_idx, text=val, is_header=is_hdr).to_dict()
            cell_records.append(c_dict)
            grid_row.append(c_dict)
        grid.append(grid_row)

    score = compute_table_alignment_score(raw_rows, expected_cols=max_cols, preset=preset)
    data_sub = raw_rows[1:] if headers else raw_rows
    clean_md = generate_markdown_table(headers=headers, rows=data_sub, alignments=column_alignments)

    return ParsedTable(
        headers=headers,
        rows=raw_rows,
        columns=columns,
        num_rows=len(raw_rows),
        num_cols=max_cols,
        cells=cell_records,
        grid=grid,
        column_alignments=column_alignments,
        markdown_table=clean_md or markdown_text.strip(),
        cell_alignment_score=score,
        is_consistent=len(set(len(r) for r in raw_rows)) <= 1,
    )


def _extract_cell_text(cell_obj: object, doc: object) -> str:
    """Extracts stripped text from a Docling table cell using document lookup with text fallback."""
    fallback = str(cell_obj.text).strip() if isinstance(cell_obj, TextItem) and cell_obj.text is not None else ""
    if isinstance(cell_obj, DocTextCell):
        try:
            return str(cell_obj._get_text(doc=doc)).strip()
        except Exception as ex:
            logger.debug("Failed cell _get_text extraction: %s", ex)
            return fallback
    return fallback


def parse_docling_table(
    item: object,
    doc: object = None,
    preset: str = "docling_fast",
) -> ParsedTable:
    """Parses a Docling TableItem into a structured ParsedTable with row and column awareness."""
    data = item.data if isinstance(item, DoclingTableItem) else None
    if data is None or not data.num_rows or not data.num_cols:
        if isinstance(item, MarkdownExportable):
            try:
                md = item.export_to_markdown(doc=doc) if doc is not None else item.export_to_markdown()
                if md:
                    return parse_markdown_table(md, preset=preset)
            except Exception as ex:
                logger.debug("Failed export_to_markdown fallback: %s", ex)
        return ParsedTable(cell_alignment_score=0.0)

    num_rows, num_cols = int(data.num_rows), int(data.num_cols)
    grid_cells = data.grid
    if not grid_cells:
        return ParsedTable(cell_alignment_score=0.0)

    raw_rows: List[List[str]] = []
    cell_confidences: List[float] = []
    for r in range(num_rows):
        row_vals: List[str] = []
        for c in range(num_cols):
            cell_obj = grid_cells[r][c] if r < len(grid_cells) and c < len(grid_cells[r]) else None
            if cell_obj is not None and isinstance(cell_obj, ConfidenceBearing) and cell_obj.confidence is not None:
                try:
                    cell_confidences.append(float(cell_obj.confidence))
                except (ValueError, TypeError) as ex:
                    logger.debug("Failed cell confidence extraction: %s", ex)
            row_vals.append(_extract_cell_text(cell_obj, doc) if cell_obj is not None else "")
        raw_rows.append(row_vals)

    headers, rows, table_title = extract_table_headers_and_title(raw_rows, num_cols, grid_cells=grid_cells)
    start_row = 1 if (table_title and len(rows) == len(raw_rows) - 1) else 0

    cell_records: List[Dict[str, Any]] = []
    grid: List[List[Dict[str, Any]]] = []
    for out_r, r in enumerate(range(start_row, num_rows)):
        grid_row: List[Dict[str, Any]] = []
        for c in range(num_cols):
            cell_obj = grid_cells[r][c] if r < len(grid_cells) and c < len(grid_cells[r]) else None
            text_val = raw_rows[r][c]
            if cell_obj is not None:
                is_hdr = (isinstance(cell_obj, HeaderCell) and bool(cell_obj.column_header)) or (
                    start_row == 1 and bool(headers and out_r == 0)
                )
                row_span = int(cell_obj.row_span) if isinstance(cell_obj, SpanningCell) else 1
                col_span = int(cell_obj.col_span) if isinstance(cell_obj, SpanningCell) else 1
                bbox_dict = (
                    {"x0": float(cell_obj.bbox.l), "y0": float(cell_obj.bbox.t),
                     "x1": float(cell_obj.bbox.r), "y1": float(cell_obj.bbox.b)}
                    if isinstance(cell_obj, BBoxBearing) and cell_obj.bbox is not None
                    else None
                )
            else:
                is_hdr = start_row == 1 and bool(headers and out_r == 0)
                row_span, col_span, bbox_dict = 1, 1, None
            c_dict = ParsedTableCell(out_r, c, text_val, row_span, col_span, is_hdr, bbox_dict).to_dict()
            cell_records.append(c_dict)
            grid_row.append(c_dict)
        grid.append(grid_row)
    num_rows = len(rows)
    columns = build_column_oriented_view(rows, num_cols)

    md_table = ""
    if isinstance(item, MarkdownExportable):
        try:
            md_table = item.export_to_markdown(doc=doc) if doc is not None else item.export_to_markdown()
        except Exception as ex:
            logger.debug("Failed export_to_markdown: %s", ex)
            md_table = ""
    if not md_table:
        md_table = generate_markdown_table(headers=headers, rows=rows[1:] if headers else rows)

    align_sc = compute_table_alignment_score(
        rows, expected_cols=num_cols, cell_confidences=cell_confidences or None, preset=preset
    )
    return ParsedTable(
        headers=headers, rows=rows, columns=columns, num_rows=num_rows, num_cols=num_cols,
        cells=cell_records, grid=grid, column_alignments=["default"] * num_cols,
        markdown_table=md_table, title=table_title, cell_alignment_score=align_sc,
        is_consistent=len(set(len(r) for r in rows)) <= 1,
    )


def parse_table_content(
    table_input: object,
    doc: object = None,
    preset: str = "docling_fast",
    fallback_text: str = "",
) -> Dict[str, Any]:
    """Parses table input from a Docling item, Markdown string, or dictionary into a node content dict."""
    if isinstance(table_input, DoclingTableItem):
        return parse_docling_table(table_input, doc=doc, preset=preset).to_dict()

    if isinstance(table_input, MarkdownExportable):
        try:
            md = table_input.export_to_markdown(doc=doc) if doc is not None else table_input.export_to_markdown()
            if md:
                return parse_markdown_table(md, preset=preset).to_dict()
        except Exception as ex:
            logger.debug("export_to_markdown failed: %s", ex)

    if isinstance(table_input, str) and "|" in table_input:
        return parse_markdown_table(table_input, preset=preset).to_dict()

    if isinstance(table_input, dict):
        rows = table_input.get("rows")
        if isinstance(rows, list):
            num_rows = len(rows)
            num_cols = max((len(r) for r in rows if isinstance(r, list)), default=0)
            headers = list(table_input.get("headers") or (rows[0] if rows else []))
            columns = table_input.get("columns") or build_column_oriented_view(rows, num_cols)
            raw_sc = table_input.get("cell_alignment_score")
            score = float(raw_sc) if raw_sc is not None else compute_table_alignment_score(rows, preset=preset)
            return {
                **table_input,
                "rows": rows,
                "columns": columns,
                "headers": headers,
                "num_rows": num_rows,
                "num_cols": num_cols,
                "cell_alignment_score": score,
                "is_consistent": len(set(len(r) for r in rows if isinstance(r, list))) <= 1,
            }

    if fallback_text and "|" in fallback_text:
        return parse_markdown_table(fallback_text, preset=preset).to_dict()

    return ParsedTable(cell_alignment_score=0.0).to_dict()


class TableParser:
    """Parser utility encapsulating table extraction with row and column awareness."""

    def __init__(self, preset: str = "docling_fast") -> None:
        self.preset = preset

    def parse(
        self,
        table_input: object,
        doc: object = None,
        fallback_text: str = "",
    ) -> ParsedTable:
        """Parses any table representation into a ParsedTable model."""
        res = parse_table_content(table_input=table_input, doc=doc, preset=self.preset, fallback_text=fallback_text)
        valid_fields = {f.name for f in fields(ParsedTable)}
        flds = {k: v for k, v in res.items() if k in valid_fields}
        return ParsedTable(**flds)

    def parse_markdown(self, markdown_text: str) -> ParsedTable:
        """Parses a Markdown table string into a ParsedTable model."""
        return parse_markdown_table(markdown_text, preset=self.preset)


__all__ = [
    "ParsedTableCell",
    "ParsedTable",
    "TableParser",
    "build_column_oriented_view",
    "compute_table_alignment_score",
    "extract_table_headers_and_title",
    "generate_html_table",
    "generate_markdown_table",
    "is_markdown_separator_row",
    "parse_column_alignments",
    "parse_docling_table",
    "parse_markdown_table",
    "parse_table_content",
    "split_markdown_row",
]
