"""
src/parsers/pypdfium_parser.py

Standalone PDF layout and text parser executing completely outside of Docling.
Uses pypdfium2 for rapid native vector text and bounding box extraction,
with automatic fallback to SectionOCRParser (RapidOCR) for scanned or image pages.
"""

import os
from typing import List, Dict, Any, Optional, Tuple

from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.parsers.synthetic_parser import SyntheticParser
from src.parsers.section_ocr import SectionOCRParser, get_default_section_parser

HAS_PYPDFIUM = False
try:
    import pypdfium2 as pdfium
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False


def _convert_pdf_rect_to_bbox(rect: Any, page_w: float, page_h: float) -> BoundingBox:
    """
    Converts a pypdfium2 rectangle (left, bottom, right, top) in PDF points
    to top-left origin BoundingBox coordinates.
    """
    l, b, r, t = rect
    x0 = max(0.0, float(min(l, r)))
    x1 = min(page_w, float(max(l, r)))
    y0 = max(0.0, float(page_h - max(t, b)))
    y1 = min(page_h, float(page_h - min(t, b)))
    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1, angle=0.0)


def _convert_ocr_box_to_bbox(
    box_coords: Optional[List[Any]],
    scale_x: float,
    scale_y: float,
    page_w: float,
    page_h: float
) -> BoundingBox:
    """Normalizes OCR polygon or bounding box coordinates to page-relative BoundingBox points."""
    if box_coords and len(box_coords) >= 4:
        bx0 = min(pt[0] for pt in box_coords) / scale_x
        by0 = min(pt[1] for pt in box_coords) / scale_y
        bx1 = max(pt[0] for pt in box_coords) / scale_x
        by1 = max(pt[1] for pt in box_coords) / scale_y
    else:
        bx0, by0, bx1, by1 = 36.0, 36.0, page_w - 36.0, page_h - 36.0
    return BoundingBox(x0=bx0, y0=by0, x1=bx1, y1=by1, angle=0.0)


def _classify_digital_node_type(text: str, is_first_on_page: bool) -> str:
    """Classifies extracted digital text as heading or paragraph."""
    is_short = len(text.split()) < 8
    is_title_case = text.isupper() or text.istitle()
    return "heading" if (is_first_on_page and is_short and is_title_case) else "paragraph"


def _classify_ocr_node_type(text: str, is_first_line: bool) -> str:
    """Classifies OCR line text as heading or paragraph."""
    is_short = len(text.split()) < 8
    return "heading" if (is_first_line and is_short) else "paragraph"


class PyPdfiumParser:
    """
    Parses PDF documents directly using pypdfium2 and targeted RapidOCR,
    operating independently of Docling for lightweight, high-throughput extraction.
    """

    def __init__(self, language: str = "en", scale: float = 2.0, min_digital_chars: int = 20):
        self.language = language.lower().strip()
        self.scale = scale
        self.min_digital_chars = min_digital_chars
        self._section_ocr: Optional[SectionOCRParser] = None

    def _get_ocr_parser(self) -> SectionOCRParser:
        if self._section_ocr is None:
            self._section_ocr = get_default_section_parser()
        return self._section_ocr

    def parse(self, pdf_path: str) -> DocumentDOM:
        """
        Parses a PDF file into DocumentDOM IR.

        For pages with embedded digital text, extracts native text rectangles.
        For scanned or image-dominant pages, renders page bitmaps and runs RapidOCR.
        """
        source_filename = os.path.basename(pdf_path)
        doc_id = f"doc_{abs(hash(source_filename)) % 1000000:06d}"

        if not HAS_PYPDFIUM or not os.path.exists(pdf_path):
            return SyntheticParser().parse(doc_id, source_filename)

        total_pages = 0
        nodes: List[DOMNode] = []
        node_counter = 1

        try:
            with pdfium.PdfDocument(pdf_path) as pdf:
                total_pages = len(pdf)
                if total_pages == 0:
                    return SyntheticParser().parse(doc_id, source_filename)

                for page_idx in range(total_pages):
                    page_no = page_idx + 1
                    page = pdf[page_idx]
                    page_nodes, node_counter = self._extract_page_nodes(
                        page=page,
                        page_no=page_no,
                        start_node_counter=node_counter
                    )
                    nodes.extend(page_nodes)
        except Exception:
            return SyntheticParser().parse(doc_id, source_filename)

        if not nodes:
            return SyntheticParser().parse(doc_id, source_filename)

        return DocumentDOM(
            document_id=doc_id,
            source_filename=source_filename,
            total_pages=total_pages,
            nodes=nodes
        )

    def _extract_page_nodes(
        self,
        page: Any,
        page_no: int,
        start_node_counter: int
    ) -> Tuple[List[DOMNode], int]:
        """
        Extracts DOM nodes from a single PDF page, selecting native digital text
        extraction or RapidOCR based on character density.
        """
        page_w, page_h = page.get_size()
        textpage = page.get_textpage()
        num_chars = textpage.count_chars()

        if num_chars >= self.min_digital_chars:
            return self._extract_digital_page_nodes(
                textpage=textpage,
                page_no=page_no,
                page_w=page_w,
                page_h=page_h,
                start_node_counter=start_node_counter
            )

        return self._extract_scanned_page_nodes(
            page=page,
            page_no=page_no,
            page_w=page_w,
            page_h=page_h,
            start_node_counter=start_node_counter
        )

    def _extract_digital_page_nodes(
        self,
        textpage: Any,
        page_no: int,
        page_w: float,
        page_h: float,
        start_node_counter: int
    ) -> Tuple[List[DOMNode], int]:
        """Extracts native digital text rectangles from a PDF textpage."""
        rect_count = textpage.count_rects()
        nodes: List[DOMNode] = []
        node_counter = start_node_counter

        for r_idx in range(rect_count):
            rect = textpage.get_rect(r_idx)
            l, b, r, t = rect
            bounded_text = textpage.get_text_bounded(l, b, r, t).strip()
            if not bounded_text:
                continue

            node_type = _classify_digital_node_type(
                bounded_text,
                is_first_on_page=(len(nodes) == 0)
            )
            bbox = _convert_pdf_rect_to_bbox(rect, page_w, page_h)

            node = DOMNode(
                node_id=f"node_p{page_no}_n{node_counter}",
                type=node_type,
                global_page_index=page_no,
                temp_slice_index=page_no,
                bounding_box=bbox,
                content={"raw_text": bounded_text, "source": "native_digital"}
            )
            nodes.append(node)
            node_counter += 1

        if not nodes:
            fallback_node = self._create_digital_fallback_node(
                textpage=textpage,
                page_no=page_no,
                page_w=page_w,
                page_h=page_h,
                node_counter=node_counter
            )
            if fallback_node is not None:
                nodes.append(fallback_node)
                node_counter += 1

        return nodes, node_counter

    @staticmethod
    def _create_digital_fallback_node(
        textpage: Any,
        page_no: int,
        page_w: float,
        page_h: float,
        node_counter: int
    ) -> Optional[DOMNode]:
        """Creates a fallback DOM node containing full page text if rects yielded nothing."""
        full_text = textpage.get_text_range().strip()
        if not full_text:
            return None

        return DOMNode(
            node_id=f"node_p{page_no}_n{node_counter}",
            type="paragraph",
            global_page_index=page_no,
            temp_slice_index=page_no,
            bounding_box=BoundingBox(x0=36.0, y0=36.0, x1=page_w - 36.0, y1=page_h - 36.0, angle=0.0),
            content={"raw_text": full_text, "source": "native_digital"}
        )

    def _extract_scanned_page_nodes(
        self,
        page: Any,
        page_no: int,
        page_w: float,
        page_h: float,
        start_node_counter: int
    ) -> Tuple[List[DOMNode], int]:
        """Renders page bitmap and executes RapidOCR for scanned or image-dominant pages."""
        ocr_parser = self._get_ocr_parser()
        try:
            rendered_pil = page.render(scale=self.scale).to_pil().convert("RGB")
            ocr_res = ocr_parser.parse_image(rendered_pil, language=self.language)
        except Exception:
            ocr_res = {"lines": []}
            rendered_pil = None

        lines = ocr_res.get("lines", [])
        if rendered_pil is not None and page_w > 0 and page_h > 0:
            scale_x = rendered_pil.width / page_w
            scale_y = rendered_pil.height / page_h
        else:
            scale_x = 1.0
            scale_y = 1.0

        nodes: List[DOMNode] = []
        node_counter = start_node_counter

        for line_idx, line in enumerate(lines):
            line_text = str(line.get("text", "")).strip()
            if not line_text:
                continue

            bbox = _convert_ocr_box_to_bbox(
                box_coords=line.get("bbox"),
                scale_x=scale_x,
                scale_y=scale_y,
                page_w=page_w,
                page_h=page_h
            )
            node_type = _classify_ocr_node_type(line_text, is_first_line=(line_idx == 0))

            node = DOMNode(
                node_id=f"node_p{page_no}_n{node_counter}",
                type=node_type,
                global_page_index=page_no,
                temp_slice_index=page_no,
                bounding_box=bbox,
                content={
                    "raw_text": line_text,
                    "confidence": line.get("confidence", 1.0),
                    "source": "rapidocr_scanned"
                }
            )
            nodes.append(node)
            node_counter += 1

        return nodes, node_counter
