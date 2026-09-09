"""
src/parsers/docling_parser.py

Docling layout parser and DocumentDOM normalizer.
Maps Docling structural items and bounding box coordinate origins into DocumentDOM IR.
"""

import os
from typing import List

from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.parsers.synthetic_parser import SyntheticParser
from src.parsers.docling_helpers import (
    LANG_CODE_MAP,
    _EXACT_LABEL_TYPES,
    fallback_top_left_bbox,
    extract_page_no_and_bbox,
    resolve_node_type,
    figure_caption,
    resolve_raw_text,
    build_node_content,
)

# Backwards compatibility re-exports
_fallback_top_left_bbox = fallback_top_left_bbox
_extract_page_no_and_bbox = extract_page_no_and_bbox
_resolve_node_type = resolve_node_type
_figure_caption = figure_caption
_resolve_raw_text = resolve_raw_text
_build_node_content = build_node_content

HAS_DOCLING = False
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    HAS_DOCLING = True
except ImportError:
    HAS_DOCLING = False


class DoclingParser:
    """Parses PDF documents using Docling layout parser and maps structural primitives into DocumentDOM."""

    def __init__(self, use_ocr: bool = True, language: str = "en", preset: str = "docling_fast"):
        self.use_ocr = use_ocr
        self.language = language.lower().strip()
        self.preset = preset

    def parse(self, pdf_path: str) -> DocumentDOM:
        source_filename = os.path.basename(pdf_path)
        doc_id = f"doc_{abs(hash(source_filename)) % 1000000:06d}"
        if HAS_DOCLING and os.path.exists(pdf_path):
            return self._parse_with_docling(pdf_path, doc_id, source_filename)
        return SyntheticParser().parse(doc_id, source_filename)

    def _parse_with_docling(self, pdf_path: str, doc_id: str, source_filename: str) -> DocumentDOM:
        ocr_langs = LANG_CODE_MAP.get(self.language, [self.language])
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self.use_ocr
        if hasattr(pipeline_options, "ocr_options") and pipeline_options.ocr_options:
            if hasattr(pipeline_options.ocr_options, "lang"):
                setattr(pipeline_options.ocr_options, "lang", ocr_langs)

        try:
            converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
            )
        except Exception:
            converter = DocumentConverter()

        doc = converter.convert(pdf_path).document
        nodes: List[DOMNode] = []
        total_pages = len(doc.pages) if hasattr(doc, "pages") and doc.pages else 1

        node_counter = 1
        for item, _ in doc.iterate_items():
            page_no, x0, y0, x1, y1, angle = 1, 0.0, 0.0, 0.0, 0.0, 0.0
            if hasattr(item, "prov") and item.prov:
                prov_item = item.prov[0]
                page_no, x0, y0, x1, y1 = extract_page_no_and_bbox(doc, item, prov_item)
                angle = getattr(item, "angle", 0.0) or getattr(prov_item, "angle", 0.0)

            node_type = resolve_node_type(item)
            dom_node = DOMNode(
                node_id=f"node_p{page_no}_n{node_counter}",
                type=node_type,
                global_page_index=page_no,
                temp_slice_index=page_no,
                bounding_box=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1, angle=float(angle)),
                content=build_node_content(item, node_type, self.preset, self.language, doc=doc)
            )
            nodes.append(dom_node)
            node_counter += 1
            total_pages = max(total_pages, page_no)

        return DocumentDOM(document_id=doc_id, source_filename=source_filename, total_pages=total_pages, nodes=nodes)
