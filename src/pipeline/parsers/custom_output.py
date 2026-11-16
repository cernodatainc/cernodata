"""
src/pipeline/parsers/custom_output.py

Shared conversion utilities normalizing custom CLI and HTTP OCR outputs
(cernodata_dom_json, markdown, hocr, text) into DocumentDOM trees.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.dom.enums import DOMNodeOrigin, DOMNodeType
from src.utils import generate_document_id

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_TABLE_SEP_RE = re.compile(r"^\|?[\s:\-]+\|[\s:\-\|]*$")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _make_sequential_bbox(idx: int, total_items: int) -> BoundingBox:
    """Computes non-overlapping vertical BoundingBox coordinates within A4 page bounds."""
    count = max(total_items, 1)
    usable_height = 760.0
    step = min(60.0, usable_height / count)
    height = max(12.0, step - 6.0)
    y0 = round(40.0 + (idx * step), 2)
    y1 = round(min(800.0, y0 + height), 2)
    if y1 <= y0:
        y1 = y0 + 10.0
    return BoundingBox(x0=40.0, y0=y0, x1=555.0, y1=y1, angle=0.0)


def _strip_hocr_markup(raw_output: str) -> str:
    """Extracts plain text blocks from hOCR HTML/XML markup when HTML tags are present."""
    if "<" not in raw_output or ">" not in raw_output:
        return raw_output
    normalized = re.sub(r"</(?:p|div|li|tr)>", "\n\n", raw_output, flags=re.IGNORECASE)
    normalized = re.sub(r"<br\s*/?>", "\n", normalized, flags=re.IGNORECASE)
    stripped = _HTML_TAG_RE.sub(" ", normalized)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in stripped.splitlines()]
    return "\n".join(lines).strip()


def _parse_table_cells(row_line: str) -> List[str]:
    trimmed = row_line.strip()
    if trimmed.startswith("|"):
        trimmed = trimmed[1:]
    if trimmed.endswith("|"):
        trimmed = trimmed[:-1]
    return [cell.strip() for cell in trimmed.split("|")]


def _parse_markdown_table(table_lines: Sequence[str]) -> Tuple[List[str], List[List[str]]]:
    parsed_rows: List[List[str]] = []
    for line in table_lines:
        stripped = line.strip()
        if _TABLE_SEP_RE.match(stripped):
            continue
        cells = _parse_table_cells(stripped)
        if cells:
            parsed_rows.append(cells)
    if not parsed_rows:
        return [], []
    headers = parsed_rows[0]
    rows = parsed_rows[1:]
    return headers, rows


def convert_plain_text_to_nodes(
    raw_text: str,
    page_index: int = 1,
    preset_id: str = "custom",
) -> List[DOMNode]:
    """Splits plain text on double newlines into paragraph DOMNode instances."""
    cleaned = raw_text.strip()
    if not cleaned:
        return []
    blocks = [blk.strip() for blk in re.split(r"\r?\n\s*\r?\n", cleaned) if blk.strip()]
    nodes: List[DOMNode] = []
    for idx, block in enumerate(blocks):
        nodes.append(
            DOMNode(
                node_id=f"{preset_id}_p{page_index}_n{idx + 1}",
                type=DOMNodeType.PARAGRAPH.value,
                global_page_index=page_index,
                temp_slice_index=page_index,
                bounding_box=_make_sequential_bbox(idx, len(blocks)),
                content={"raw_text": block},
                origin=DOMNodeOrigin.PARSED.value,
            )
        )
    return nodes


def convert_markdown_to_nodes(
    markdown_text: str,
    page_index: int = 1,
    preset_id: str = "custom",
) -> List[DOMNode]:
    """Splits markdown headings (#), tables (|), and text paragraphs into DOMNode instances."""
    lines = markdown_text.splitlines()
    raw_items: List[Tuple[str, Dict[str, Any]]] = []
    para_buf: List[str] = []

    def _flush_para() -> None:
        if para_buf:
            text = "\n".join(para_buf).strip()
            para_buf.clear()
            if text:
                raw_items.append((DOMNodeType.PARAGRAPH.value, {"raw_text": text}))

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if not stripped:
            _flush_para()
            idx += 1
            continue

        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            _flush_para()
            hashes, title = heading_match.groups()
            raw_items.append((
                DOMNodeType.HEADING.value,
                {"raw_text": title.strip(), "level": len(hashes)},
            ))
            idx += 1
            continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            _flush_para()
            table_lines: List[str] = []
            while idx < len(lines):
                t_line = lines[idx].strip()
                if not t_line.startswith("|"):
                    break
                table_lines.append(t_line)
                idx += 1
            headers, rows = _parse_markdown_table(table_lines)
            raw_items.append((
                DOMNodeType.TABLE_GRID.value,
                {
                    "raw_text": "\n".join(table_lines),
                    "headers": headers,
                    "rows": rows,
                },
            ))
            continue

        para_buf.append(line.rstrip())
        idx += 1

    _flush_para()

    nodes: List[DOMNode] = []
    for item_idx, (node_type, content) in enumerate(raw_items):
        nodes.append(
            DOMNode(
                node_id=f"{preset_id}_p{page_index}_n{item_idx + 1}",
                type=node_type,
                global_page_index=page_index,
                temp_slice_index=page_index,
                bounding_box=_make_sequential_bbox(item_idx, len(raw_items)),
                content=content,
                origin=DOMNodeOrigin.PARSED.value,
            )
        )
    return nodes


def convert_dom_dict_to_dom(
    payload: Mapping[str, Any],
    resolved_path: str,
    preset_id: str = "custom",
) -> DocumentDOM:
    """Builds a DocumentDOM from a serialized DOM JSON mapping."""
    normalized: Dict[str, Any] = dict(payload)
    if not normalized.get("document_id"):
        normalized["document_id"] = generate_document_id(resolved_path)
    if not normalized.get("source_filename"):
        normalized["source_filename"] = os.path.basename(resolved_path)
    dom = DocumentDOM.from_dict(normalized)
    dom.recompute_total_pages()
    dom.metadata.setdefault("preset", preset_id)
    return dom


def convert_raw_output_to_dom(
    raw_output: str,
    resolved_path: str,
    output_format: str = "text",
    preset_id: str = "custom",
    page_index: int = 1,
) -> DocumentDOM:
    """Converts raw text, markdown, hocr, or cernodata_dom_json output into a DocumentDOM."""
    fmt = (output_format or "text").strip().lower()
    if fmt == "cernodata_dom_json":
        parsed = json.loads(raw_output)
        if isinstance(parsed, list):
            parsed = {"nodes": parsed}
        if not isinstance(parsed, Mapping):
            raise ValueError("cernodata_dom_json output must decode to a JSON object or node list.")
        return convert_dom_dict_to_dom(parsed, resolved_path=resolved_path, preset_id=preset_id)

    if fmt == "markdown":
        nodes = convert_markdown_to_nodes(raw_output, page_index=page_index, preset_id=preset_id)
    else:
        text_content = _strip_hocr_markup(raw_output) if fmt == "hocr" else raw_output
        nodes = convert_plain_text_to_nodes(text_content, page_index=page_index, preset_id=preset_id)

    total_pages = max((n.global_page_index for n in nodes), default=1)
    return DocumentDOM(
        document_id=generate_document_id(resolved_path),
        source_filename=os.path.basename(resolved_path),
        total_pages=total_pages,
        nodes=nodes,
        metadata={"preset": preset_id, "output_format": fmt},
    )


__all__ = [
    "convert_dom_dict_to_dom",
    "convert_markdown_to_nodes",
    "convert_plain_text_to_nodes",
    "convert_raw_output_to_dom",
]
