"""
src/parsers/docling_parser.py

Docling layout parser and DocumentDOM normalizer.
Maps Docling structural items and bounding box coordinate origins into DocumentDOM IR.
"""

from __future__ import annotations

import os
import logging
from typing import Callable, Dict, List, Optional, Tuple

from src.utils import generate_document_id, resolve_and_validate_pdf_path
from src.dom import BoundingBox, DOMNode, DocumentDOM

logger = logging.getLogger("cernodata.docling_parser")
from src.parsers.docling_helpers import (
    LANG_CODE_MAP,
    build_node_content,
    extract_page_no_and_bbox,
    resolve_node_type,
)
from src.parsers.docling_types import (
    AngleBearing,
    DoclingDocument,
    OcrLangConfigurable,
    OcrModeConfigurable,
    OcrScaleConfigurable,
    ProvenanceBearing,
)

HAS_DOCLING = False
try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import (
        EasyOcrOptions,
        OcrMode,
        OcrOptions,
        PdfPipelineOptions,
        RapidOcrOptions,
        TesseractOcrOptions,
    )
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

    def build_pipeline_options(self) -> Optional[PdfPipelineOptions]:
        """Constructs and configures PdfPipelineOptions and specialized OCR options."""
        if not HAS_DOCLING:
            return None

        ocr_langs = LANG_CODE_MAP.get(self.language, [self.language] if self.language else ["pl", "de", "fr", "es", "en"])
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self.use_ocr
        pipeline_options.do_table_structure = self.do_table_structure
        pipeline_options.images_scale = self.ocr_scale

        ocr_mode = OcrMode.FULL_PAGE if self.force_full_page_ocr else OcrMode.DEFAULT

        # Configure specialized OCR engine options if available
        engine = self.ocr_engine
        if engine == "auto" and self.preset == "docling_fast":
            engine = "rapidocr"

        def _instantiate_ocr_options(
            factory: Callable[[], OcrOptions],
            fallback_factory: Callable[[], OcrOptions],
            label: str,
        ) -> Optional[OcrOptions]:
            try:
                return factory()
            except TypeError as te:
                logger.debug("Failed initializing %s with mode; retrying with scale only: %s", label, te)
                try:
                    return fallback_factory()
                except Exception as ex:
                    logger.warning("Failed initializing OCR options for %s: %s", label, ex)
                    return None
            except Exception as ex:
                logger.warning("Unexpected error creating %s: %s", label, ex)
                return None

        engine_factories: Dict[str, Tuple[str, Callable[[], OcrOptions], Callable[[], OcrOptions]]] = {
            "rapidocr": (
                "RapidOcrOptions",
                lambda: RapidOcrOptions(mode=ocr_mode, scale=self.ocr_scale, backend="torch"),
                lambda: RapidOcrOptions(scale=self.ocr_scale, backend="torch"),
            ),
            "tesseract": (
                "TesseractOcrOptions",
                lambda: TesseractOcrOptions(mode=ocr_mode, scale=self.ocr_scale),
                lambda: TesseractOcrOptions(scale=self.ocr_scale),
            ),
            "tesseract_cli": (
                "TesseractOcrOptions",
                lambda: TesseractOcrOptions(mode=ocr_mode, scale=self.ocr_scale),
                lambda: TesseractOcrOptions(scale=self.ocr_scale),
            ),
            "easyocr": (
                "EasyOcrOptions",
                lambda: EasyOcrOptions(mode=ocr_mode, scale=self.ocr_scale),
                lambda: EasyOcrOptions(scale=self.ocr_scale),
            ),
        }
        ocr_opts: Optional[OcrOptions] = None
        if engine in engine_factories:
            label, factory, fallback_factory = engine_factories[engine]
            try:
                ocr_opts = _instantiate_ocr_options(factory, fallback_factory, label)
            except Exception as ex:
                logger.warning("%s engine option configuration failed: %s", engine, ex)

        if ocr_opts is not None:
            pipeline_options.ocr_options = ocr_opts

        current_ocr_opts = pipeline_options.ocr_options
        if current_ocr_opts is not None:
            if isinstance(current_ocr_opts, OcrLangConfigurable):
                current_ocr_opts.lang = ocr_langs
            if isinstance(current_ocr_opts, OcrScaleConfigurable):
                current_ocr_opts.scale = self.ocr_scale
            if isinstance(current_ocr_opts, OcrModeConfigurable):
                current_ocr_opts.mode = ocr_mode

        return pipeline_options

    def parse(self, pdf_path: str) -> DocumentDOM:
        resolved_path = resolve_and_validate_pdf_path(pdf_path)
        if not HAS_DOCLING:
            raise RuntimeError("Docling library is not installed or available in this Python environment.")

        source_filename = os.path.basename(resolved_path)
        doc_id = generate_document_id(source_filename)
        return self._parse_with_docling(resolved_path, doc_id, source_filename)

    def _parse_with_docling(self, pdf_path: str, doc_id: str, source_filename: str) -> DocumentDOM:
        pipeline_options = self.build_pipeline_options()

        try:
            converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
            )
        except Exception as e:
            logger.warning(
                "Failed to initialize DocumentConverter with custom pipeline options: %s. Falling back to default options.",
                e
            )
            converter = DocumentConverter()

        doc = converter.convert(pdf_path).document
        nodes: List[DOMNode] = []
        total_pages = len(doc.pages) if isinstance(doc, DoclingDocument) and doc.pages else 1

        node_counter = 1
        for item, _ in doc.iterate_items():
            page_no, x0, y0, x1, y1, angle = 1, 0.0, 0.0, 0.0, 0.0, 0.0
            if isinstance(item, ProvenanceBearing) and item.prov:
                prov_item = item.prov[0]
                page_no, x0, y0, x1, y1 = extract_page_no_and_bbox(doc, item, prov_item)
                item_angle = item.angle if isinstance(item, AngleBearing) and item.angle else 0.0
                prov_angle = prov_item.angle if isinstance(prov_item, AngleBearing) and prov_item.angle else 0.0
                angle = item_angle or prov_angle

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


# Backwards-compatible aliases for legacy test suites
from src.parsers.docling_helpers import (
    resolve_node_type as _resolve_node_type,
    build_node_content as _build_node_content,
    resolve_raw_text as _resolve_raw_text,
)

__all__ = [
    "DoclingParser",
    "_resolve_node_type",
    "_build_node_content",
    "_resolve_raw_text",
]
