"""
src/parsers/pypdfium_parser.py

Standalone PDF layout and text parser executing completely outside of Docling.
Uses pypdfium2 for rapid native vector text and bounding box extraction,
with automatic fallback to SectionOCRParser (RapidOCR) for scanned or image pages.
"""

import os
from typing import List, Dict, Any, Optional

from src.dom import BoundingBox, DOMNode, DocumentDOM
from src.parsers.synthetic_parser import SyntheticParser
from src.parsers.section_ocr import SectionOCRParser, get_default_section_parser

HAS_PYPDFIUM = False
try:
    import pypdfium2 as pdfium
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False


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

        try:
            pdf = pdfium.PdfDocument(pdf_path)
        except Exception:
            return SyntheticParser().parse(doc_id, source_filename)

        total_pages = len(pdf)
        if total_pages == 0:
            return SyntheticParser().parse(doc_id, source_filename)

        nodes: List[DOMNode] = []
        node_counter = 1

        for page_idx in range(total_pages):
            page_no = page_idx + 1
            page = pdf[page_idx]
            page_w, page_h = page.get_size()

            textpage = page.get_textpage()
            num_chars = textpage.count_chars()

            if num_chars >= self.min_digital_chars:
                # Digital page: extract native text rectangles
                rect_count = textpage.count_rects()
                extracted_on_page = 0

                for r_idx in range(rect_count):
                    rect = textpage.get_rect(r_idx)
                    # pypdfium2 rect is (left, bottom, right, top) in PDF points
                    l, b, r, t = rect
                    x0 = max(0.0, float(min(l, r)))
                    x1 = min(page_w, float(max(l, r)))
                    # Convert to top-left origin
                    y0 = max(0.0, float(page_h - max(t, b)))
                    y1 = min(page_h, float(page_h - min(t, b)))

                    bounded_text = textpage.get_text_bounded(l, b, r, t).strip()
                    if not bounded_text:
                        continue

                    # Classify node type
                    is_short = len(bounded_text.split()) < 8
                    is_title_case = bounded_text.isupper() or bounded_text.istitle()
                    node_type = "heading" if (extracted_on_page == 0 and is_short and is_title_case) else "paragraph"

                    node = DOMNode(
                        node_id=f"node_p{page_no}_n{node_counter}",
                        type=node_type,
                        global_page_index=page_no,
                        temp_slice_index=page_no,
                        bounding_box=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1, angle=0.0),
                        content={"raw_text": bounded_text, "source": "native_digital"}
                    )
                    nodes.append(node)
                    node_counter += 1
                    extracted_on_page += 1

                if extracted_on_page == 0:
                    # Fallback to full page text if rects yielded nothing
                    full_text = textpage.get_text_range().strip()
                    if full_text:
                        nodes.append(DOMNode(
                            node_id=f"node_p{page_no}_n{node_counter}",
                            type="paragraph",
                            global_page_index=page_no,
                            temp_slice_index=page_no,
                            bounding_box=BoundingBox(x0=36.0, y0=36.0, x1=page_w - 36.0, y1=page_h - 36.0, angle=0.0),
                            content={"raw_text": full_text, "source": "native_digital"}
                        ))
                        node_counter += 1
            else:
                # Scanned or image page: render and execute targeted OCR
                ocr_parser = self._get_ocr_parser()
                try:
                    rendered_pil = page.render(scale=self.scale).to_pil().convert("RGB")
                    ocr_res = ocr_parser.parse_image(rendered_pil, language=self.language)
                except Exception:
                    ocr_res = {"lines": []}

                lines = ocr_res.get("lines", [])
                scale_x = rendered_pil.width / page_w if page_w > 0 else 1.0
                scale_y = rendered_pil.height / page_h if page_h > 0 else 1.0

                for line_idx, line in enumerate(lines):
                    line_text = str(line.get("text", "")).strip()
                    if not line_text:
                        continue

                    box_coords = line.get("bbox")
                    if box_coords and len(box_coords) >= 4:
                        bx0 = min(pt[0] for pt in box_coords) / scale_x
                        by0 = min(pt[1] for pt in box_coords) / scale_y
                        bx1 = max(pt[0] for pt in box_coords) / scale_x
                        by1 = max(pt[1] for pt in box_coords) / scale_y
                    else:
                        bx0, by0, bx1, by1 = 36.0, 36.0, page_w - 36.0, page_h - 36.0

                    node_type = "heading" if line_idx == 0 and len(line_text.split()) < 8 else "paragraph"

                    node = DOMNode(
                        node_id=f"node_p{page_no}_n{node_counter}",
                        type=node_type,
                        global_page_index=page_no,
                        temp_slice_index=page_no,
                        bounding_box=BoundingBox(x0=bx0, y0=by0, x1=bx1, y1=by1, angle=0.0),
                        content={
                            "raw_text": line_text,
                            "confidence": line.get("confidence", 1.0),
                            "source": "rapidocr_scanned"
                        }
                    )
                    nodes.append(node)
                    node_counter += 1

        if not nodes:
            return SyntheticParser().parse(doc_id, source_filename)

        return DocumentDOM(
            document_id=doc_id,
            source_filename=source_filename,
            total_pages=total_pages,
            nodes=nodes
        )
