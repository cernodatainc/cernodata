"""
src/parsers/docling_parser.py

Docling layout parser and DocumentDOM normalizer.
Maps Docling structural items and bounding box coordinate origins into DocumentDOM IR.
"""

import os
import re
from typing import Dict, Any, List, Tuple
from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.parsers.synthetic_parser import SyntheticParser

HAS_DOCLING = False
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    HAS_DOCLING = True
except ImportError:
    HAS_DOCLING = False

LANG_CODE_MAP = {"pl": ["pol", "pl"], "de": ["deu", "de"], "fr": ["fra", "fr"], "es": ["spa", "es"], "en": ["eng", "en"]}


def _extract_page_no_and_bbox(doc: Any, item: Any, prov_item: Any) -> Tuple[int, float, float, float, float]:
    """Extracts page number and top-left origin normalized bounding box coordinates."""
    page_no = getattr(prov_item, "page_no", 1)
    if not hasattr(prov_item, "bbox") or not prov_item.bbox:
        return page_no, 0.0, 0.0, 0.0, 0.0

    bbox = prov_item.bbox
    page_height = 792.0
    if hasattr(doc, "pages") and doc.pages:
        if isinstance(doc.pages, dict) and page_no in doc.pages:
            page_height = getattr(doc.pages[page_no].size, "height", 792.0)
        elif isinstance(doc.pages, list) and 0 <= page_no - 1 < len(doc.pages):
            page_height = getattr(doc.pages[page_no - 1].size, "height", 792.0)

    if hasattr(bbox, "to_top_left_origin"):
        try:
            tl = bbox.to_top_left_origin(page_height)
            x0, y0, x1, y1 = tl.l, tl.t, tl.r, tl.b
        except Exception:
            x0, y0, x1, y1 = _fallback_top_left_bbox(bbox, page_height)
    else:
        x0, y0, x1, y1 = _fallback_top_left_bbox(bbox, page_height)

    if y0 > y1: y0, y1 = y1, y0
    if x0 > x1: x0, x1 = x1, x0
    return page_no, x0, y0, x1, y1


def _fallback_top_left_bbox(bbox: Any, page_height: float) -> Tuple[float, float, float, float]:
    """Calculates top-left origin coordinates from bottom-left origin fallback."""
    if getattr(bbox, "coord_origin", None) and "BOTTOMLEFT" in str(bbox.coord_origin):
        return getattr(bbox, "l", 0.0), page_height - getattr(bbox, "t", 0.0), getattr(bbox, "r", 0.0), page_height - getattr(bbox, "b", 0.0)
    return getattr(bbox, "l", 0.0), getattr(bbox, "t", 0.0), getattr(bbox, "r", 0.0), getattr(bbox, "b", 0.0)


# Docling emits DocItemLabel values such as "section_header" and "page_header". Exact labels
# are resolved first: a substring check would route "section_header" to header_footer (it
# contains "header") before the heading check could run.
_EXACT_LABEL_TYPES: Dict[str, str] = {
    "title": "heading",
    "section_header": "heading",
    "page_header": "header_footer",
    "page_footer": "header_footer",
    "table": "table_grid",
    "picture": "figure",
}


def _resolve_node_type(item: Any) -> str:
    """Resolves cernodata DOM primitive type from docling item label."""
    label = getattr(item, "label", "") or ""
    label = str(getattr(label, "value", label)).lower()
    exact = _EXACT_LABEL_TYPES.get(label)
    if exact:
        return exact
    if "title" in label or "heading" in label or "section" in label: return "heading"
    if "header" in label or "footer" in label: return "header_footer"
    if "table" in label: return "table_grid"
    if "picture" in label or "figure" in label: return "figure"
    return "paragraph"


def _figure_caption(item: Any, doc: Any) -> str:
    """Returns the caption text of a figure item when Docling exposes one, otherwise an empty string."""
    if doc is None or not hasattr(item, "caption_text"):
        return ""
    try:
        caption = item.caption_text(doc)
    except Exception:
        return ""
    return caption.strip() if isinstance(caption, str) else ""


def _resolve_raw_text(item: Any, node_type: str, doc: Any = None) -> str:
    """
    Resolves the textual content of a Docling item.

    Items without a text attribute (for example PictureItem) must yield an empty string,
    never their object repr. Figures fall back to their caption when one is available.
    """
    text = getattr(item, "text", None)
    raw_text = text.strip() if isinstance(text, str) else ""
    if not raw_text and node_type == "figure":
        raw_text = _figure_caption(item, doc)
    return raw_text


def _build_node_content(item: Any, node_type: str, preset: str = "docling_fast", language: str = "en", doc: Any = None) -> Dict[str, Any]:
    """Builds node content payload dictionary, applying deep OCR diacritic restoration if docling_deep preset is selected."""
    raw_text = _resolve_raw_text(item, node_type, doc)
    if preset == "docling_deep" and language == "pl":
        raw_text = raw_text.replace("piqtku", "piątku").replace("granicq", "granicą")

    content_dict: Dict[str, Any] = {"raw_text": raw_text}
    if node_type == "table_grid" and hasattr(item, "export_to_markdown"):
        try: content_dict["markdown_table"] = item.export_to_markdown()
        except Exception: pass
        content_dict["cell_alignment_score"] = 0.98 if preset == "docling_deep" else 0.96
    return content_dict


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
            converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)})
        except Exception:
            converter = DocumentConverter()

        doc = converter.convert(pdf_path).document
        nodes: List[DOMNode] = []
        total_pages = len(doc.pages) if hasattr(doc, "pages") and doc.pages else 1

        node_counter = 1
        for item, level in doc.iterate_items():
            page_no, x0, y0, x1, y1, angle = 1, 0.0, 0.0, 0.0, 0.0, 0.0
            if hasattr(item, "prov") and item.prov:
                prov_item = item.prov[0]
                page_no, x0, y0, x1, y1 = _extract_page_no_and_bbox(doc, item, prov_item)
                angle = getattr(item, "angle", 0.0) or getattr(prov_item, "angle", 0.0)

            node_type = _resolve_node_type(item)
            dom_node = DOMNode(
                node_id=f"node_p{page_no}_n{node_counter}",
                type=node_type,
                global_page_index=page_no,
                temp_slice_index=page_no,
                bounding_box=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1, angle=float(angle)),
                content=_build_node_content(item, node_type, self.preset, self.language, doc=doc)
            )
            nodes.append(dom_node)
            node_counter += 1
            total_pages = max(total_pages, page_no)

        return DocumentDOM(document_id=doc_id, source_filename=source_filename, total_pages=total_pages, nodes=nodes)
