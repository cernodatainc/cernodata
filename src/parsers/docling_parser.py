"""
src/parsers/docling_parser.py

Docling layout parser and DocumentDOM normalizer.
Maps Docling structural items and bounding box coordinate origins into DocumentDOM IR.
"""

from __future__ import annotations

import os
from typing import List, Optional, Any

from src.utils import resolve_pdf_path
from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.parsers.docling_helpers import (
    LANG_CODE_MAP,
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
    from docling.datamodel.pipeline_options import PdfPipelineOptions, OcrMode
    from docling.datamodel.base_models import InputFormat
    HAS_DOCLING = True
except ImportError:
    HAS_DOCLING = False


class DoclingParser:
    """Parses PDF documents using Docling layout parser and maps structural primitives into DocumentDOM."""

    def __init__(
        self,
        use_ocr: bool = True,
        language: Optional[str] = "en",
        preset: str = "docling_fast",
        ocr_engine: str = "auto",
        ocr_scale: Optional[float] = None,
        force_full_page_ocr: bool = False,
        do_table_structure: bool = True,
    ) -> None:
        self.use_ocr = use_ocr
        self.language = language.lower().strip() if language else ""
        self.preset = preset
        self.ocr_engine = ocr_engine.lower().strip()
        self.ocr_scale = ocr_scale if ocr_scale is not None else (3.5 if preset == "docling_deep" else 3.0)
        self.force_full_page_ocr = force_full_page_ocr
        self.do_table_structure = do_table_structure

    def build_pipeline_options(self) -> Any:
        """Constructs and configures PdfPipelineOptions and specialized OCR options."""
        if not HAS_DOCLING:
            return None

        ocr_langs = LANG_CODE_MAP.get(self.language, [self.language] if self.language else ["pl", "de", "fr", "es", "en"])
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self.use_ocr
        pipeline_options.do_table_structure = self.do_table_structure
        if hasattr(pipeline_options, "images_scale"):
            pipeline_options.images_scale = self.ocr_scale

        ocr_mode = OcrMode.FULL_PAGE if self.force_full_page_ocr else OcrMode.DEFAULT

        # Configure specialized OCR engine options if available
        engine = self.ocr_engine
        if engine == "auto" and self.preset == "docling_fast":
            engine = "rapidocr"

        def _instantiate_ocr_options(cls: Any, **extra_kwargs: Any) -> Any:
            try:
                return cls(mode=ocr_mode, scale=self.ocr_scale, **extra_kwargs)
            except Exception:
                try:
                    return cls(scale=self.ocr_scale, **extra_kwargs)
                except Exception:
                    return None

        ocr_opts = None
        if engine == "rapidocr":
            try:
                from docling.datamodel.pipeline_options import RapidOcrOptions
                ocr_opts = _instantiate_ocr_options(RapidOcrOptions, backend="torch")
            except Exception:
                pass
        elif engine in ("tesseract", "tesseract_cli"):
            try:
                from docling.datamodel.pipeline_options import TesseractOcrOptions
                ocr_opts = _instantiate_ocr_options(TesseractOcrOptions)
            except Exception:
                pass
        elif engine == "easyocr":
            try:
                from docling.datamodel.pipeline_options import EasyOcrOptions
                ocr_opts = _instantiate_ocr_options(EasyOcrOptions)
            except Exception:
                pass

        if ocr_opts is not None:
            pipeline_options.ocr_options = ocr_opts

        if hasattr(pipeline_options, "ocr_options") and pipeline_options.ocr_options:
            if hasattr(pipeline_options.ocr_options, "lang"):
                setattr(pipeline_options.ocr_options, "lang", ocr_langs)
            if hasattr(pipeline_options.ocr_options, "scale"):
                setattr(pipeline_options.ocr_options, "scale", self.ocr_scale)
            if hasattr(pipeline_options.ocr_options, "mode"):
                setattr(pipeline_options.ocr_options, "mode", ocr_mode)

        return pipeline_options

    def parse(self, pdf_path: str) -> DocumentDOM:
        resolved_path = resolve_pdf_path(pdf_path)
        if not os.path.exists(resolved_path):
            raise FileNotFoundError(f"PDF document not found: '{pdf_path}'")
        if not HAS_DOCLING:
            raise RuntimeError("Docling library is not installed or available in this Python environment.")

        source_filename = os.path.basename(resolved_path)
        doc_id = f"doc_{abs(hash(source_filename)) % 1000000:06d}"
        return self._parse_with_docling(resolved_path, doc_id, source_filename)

    def _parse_with_docling(self, pdf_path: str, doc_id: str, source_filename: str) -> DocumentDOM:
        pipeline_options = self.build_pipeline_options()

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
