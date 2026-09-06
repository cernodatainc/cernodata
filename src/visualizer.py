"""
src/visualizer.py

Page-Level Bounding Box Layout Visualizer & Provenance Overlay Engine.
Renders input PDF pages to high-resolution images and overlays color-coded bounding boxes,
type labels, quality violation callouts (e.g. '[!] VIOLATION: piqtku'), and bottom-left confidence badges.
"""

import os
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from src.dom import DocumentDOM, DOMNode

HAS_PYPDFIUM = False
try:
    import pypdfium2
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False


COLOR_PALETTE = {
    "heading": {"stroke": "#1976D2", "fill": "#1976D222", "label_bg": "#1976D2"},
    "paragraph": {"stroke": "#388E3C", "fill": "#388E3C22", "label_bg": "#388E3C"},
    "table_grid": {"stroke": "#7B1FA2", "fill": "#7B1FA233", "label_bg": "#7B1FA2"},
    "figure": {"stroke": "#F57C00", "fill": "#F57C0022", "label_bg": "#F57C00"},
    "header_footer": {"stroke": "#616161", "fill": "#61616122", "label_bg": "#616161"}
}


class PageVisualizer:
    """
    Renders PDF page overlays with parsed DOM bounding box annotations and quality violation markers.
    """

    def __init__(self, dpi: int = 150):
        self.dpi = dpi
        self.scale = dpi / 72.0  # PDF points to pixel scale factor

    def render_overlay(
        self,
        pdf_path: str,
        dom: DocumentDOM,
        violations: Optional[List[Dict[str, Any]]] = None,
        output_dir: str = "output"
    ) -> List[str]:
        os.makedirs(output_dir, exist_ok=True)
        output_paths = []
        violations = violations or []

        # Group nodes and violations by page
        page_nodes: Dict[int, List[DOMNode]] = {p: [] for p in range(1, dom.total_pages + 1)}
        for node in dom.nodes:
            page_nodes.setdefault(node.global_page_index, []).append(node)

        page_violations: Dict[int, List[Dict[str, Any]]] = {p: [] for p in range(1, dom.total_pages + 1)}
        for v in violations:
            p_idx = v.get("global_page_index", 1)
            page_violations.setdefault(p_idx, []).append(v)

        if HAS_PYPDFIUM and os.path.exists(pdf_path):
            try:
                pdf = pypdfium2.PdfDocument(pdf_path)
                for page_idx in range(len(pdf)):
                    page_no = page_idx + 1
                    pdf_page = pdf[page_idx]
                    page_w, page_h = pdf_page.get_size()

                    pil_img = pdf_page.render(scale=self.scale).to_pil().convert("RGBA")
                    nodes_for_page = page_nodes.get(page_no, [])
                    viols_for_page = page_violations.get(page_no, [])

                    overlay_img = self._draw_nodes_on_image(
                        pil_img, page_no, page_w, page_h, nodes_for_page, viols_for_page
                    )
                    
                    out_path = os.path.join(output_dir, f"overlay_page_{page_no}.png")
                    overlay_img.save(out_path)
                    output_paths.append(out_path)
                return output_paths
            except Exception as e:
                print(f"[WARN] pypdfium2 rendering failed ({e}), using synthetic visualizer fallback.")

        # Fallback synthetic canvas generator
        for page_no, nodes_for_page in page_nodes.items():
            canvas_w, canvas_h = int(612 * self.scale), int(792 * self.scale)
            pil_img = Image.new("RGBA", (canvas_w, canvas_h), (245, 247, 250, 255))
            viols_for_page = page_violations.get(page_no, [])
            overlay_img = self._draw_nodes_on_image(
                pil_img, page_no, 612.0, 792.0, nodes_for_page, viols_for_page
            )
            out_path = os.path.join(output_dir, f"overlay_page_{page_no}.png")
            overlay_img.save(out_path)
            output_paths.append(out_path)

        return output_paths

    def _draw_nodes_on_image(
        self,
        base_img: Image.Image,
        page_no: int,
        page_w: float,
        page_h: float,
        nodes: List[DOMNode],
        violations: List[Dict[str, Any]]
    ) -> Image.Image:
        img_w, img_h = base_img.size
        sx = img_w / page_w if page_w > 0 else self.scale
        sy = img_h / page_h if page_h > 0 else self.scale

        overlay = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_base = ImageDraw.Draw(base_img)

        # Index violations by node_id
        node_violations: Dict[str, List[Dict[str, Any]]] = {}
        for v in violations:
            nid = v.get("node_id")
            if nid:
                node_violations.setdefault(nid, []).append(v)

        try:
            font = ImageFont.truetype("arial.ttf", max(11, int(11 * (self.dpi / 150))))
            header_font = ImageFont.truetype("arial.ttf", max(13, int(13 * (self.dpi / 150))))
        except IOError:
            font = ImageFont.load_default()
            header_font = font

        for node in nodes:
            bbox = node.bounding_box
            x0 = bbox.x0 * sx
            y0 = bbox.y0 * sy
            x1 = bbox.x1 * sx
            y1 = bbox.y1 * sy

            if x1 <= x0:
                x1 = x0 + 20
            if y1 <= y0:
                y1 = y0 + 15

            palette = COLOR_PALETTE.get(node.type, COLOR_PALETTE["paragraph"])
            stroke_col = palette["stroke"]

            # Check if node has quality violations
            active_viols = node_violations.get(node.node_id, [])
            has_violation = len(active_viols) > 0

            if has_violation:
                stroke_col = "#FF1744"  # Bright red for violation box
                draw_overlay.rectangle([x0, y0, x1, y1], outline="#FF1744", width=4)
            else:
                draw_overlay.rectangle([x0, y0, x1, y1], outline=stroke_col, width=3)

            # Node label badge
            label_text = f"[{node.type}] {node.node_id}"
            left, top, right, bottom = font.getbbox(label_text)
            text_w = right - left
            text_h = bottom - top

            badge_x0 = x0
            badge_y0 = max(0, y0 - text_h - 4)
            badge_x1 = badge_x0 + text_w + 8
            badge_y1 = badge_y0 + text_h + 4

            draw_base.rectangle([badge_x0, badge_y0, badge_x1, badge_y1], fill=stroke_col)
            draw_base.text((badge_x0 + 4, badge_y0 + 2), label_text, fill="white", font=font)

            # Draw violation callout marker badge if violations exist on node
            if has_violation:
                v = active_viols[0]
                snippet = v.get("detected_snippet", "")
                suggested = v.get("suggested_correction", "")
                viol_label = f"[!] VIOLATION: '{snippet}'"
                if suggested:
                    viol_label += f" -> '{suggested}'"

                v_left, v_top, v_right, v_bottom = font.getbbox(viol_label)
                v_w = v_right - v_left
                v_h = v_bottom - v_top

                v_x0 = x0
                v_y0 = badge_y1 + 2
                v_x1 = v_x0 + v_w + 10
                v_y1 = v_y0 + v_h + 6

                draw_base.rectangle([v_x0, v_y0, v_x1, v_y1], fill="#D50000", outline="yellow", width=1)
                draw_base.text((v_x0 + 5, v_y0 + 3), viol_label, fill="white", font=font)

        # Merge translucent overlay
        result_img = Image.alpha_composite(base_img, overlay).convert("RGB")
        draw_result = ImageDraw.Draw(result_img)

        # Top banner summary
        banner_h = 32
        draw_result.rectangle([0, 0, img_w, banner_h], fill="#1E1E2F")
        draw_result.text(
            (12, 6),
            f"cernodata Visual Provenance Overlay | Page {page_no} | Nodes: {len(nodes)} | Violations: {len(violations)}",
            fill="#FF5252" if len(violations) > 0 else "#00E676",
            font=header_font
        )

        # Bottom-left confidence score & violation summary badge
        self._draw_score_badge_bottom_left(
            draw_result, img_w, img_h, page_no, nodes, violations, font, header_font
        )

        return result_img

    def _draw_score_badge_bottom_left(
        self,
        draw: ImageDraw.ImageDraw,
        img_w: int,
        img_h: int,
        page_no: int,
        nodes: List[DOMNode],
        violations: List[Dict[str, Any]],
        font: ImageFont.ImageFont,
        header_font: ImageFont.ImageFont
    ):
        """Renders overall confidence score & violation summary badge in bottom-left corner."""
        try:
            from src.heuristics import evaluate_page_confidence
        except ImportError:
            from heuristics import evaluate_page_confidence

        page_score = round(evaluate_page_confidence(nodes), 3)
        status_text = "ACCEPT" if page_score >= 0.82 else "FALLBACK"
        status_color = "#00E676" if page_score >= 0.82 else "#FF5252"

        line1 = f"Page {page_no} Confidence Score: {page_score:.3f}"
        line2 = f"Decision Status: {status_text} | Violations Flagged: {len(violations)}"

        l1_bbox = header_font.getbbox(line1)
        l2_bbox = font.getbbox(line2)

        w1 = l1_bbox[2] - l1_bbox[0]
        w2 = l2_bbox[2] - l2_bbox[0]
        badge_w = max(w1, w2) + 24
        badge_h = 54

        margin = 16
        bx0 = margin
        by1 = img_h - margin
        by0 = by1 - badge_h
        bx1 = bx0 + badge_w

        draw.rectangle([bx0, by0, bx1, by1], fill="#111827", outline=status_color, width=2)
        draw.text((bx0 + 12, by0 + 8), line1, fill="white", font=header_font)
        draw.text((bx0 + 12, by0 + 28), line2, fill=status_color, font=font)
