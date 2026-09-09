"""
src/visualization/overlay.py

Page-Level Bounding Box Layout Visualizer & Provenance Overlay Engine.
Supports text-alignment rotated bounding boxes, violation callouts, and bottom-left score badges.
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
from src.dom import DocumentDOM, DOMNode
from src.visualization.badges import draw_score_badge_bottom_left
from src.visualization.callouts import draw_violation_callout

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


def _group_by_page(dom: DocumentDOM, violations: List[Dict[str, Any]]) -> Tuple[Dict[int, List[DOMNode]], Dict[int, List[Dict[str, Any]]]]:
    """Groups DOM nodes and quality violation records by page index."""
    page_nodes: Dict[int, List[DOMNode]] = {p: [] for p in range(1, dom.total_pages + 1)}
    for node in dom.nodes:
        page_nodes.setdefault(node.global_page_index, []).append(node)

    page_violations: Dict[int, List[Dict[str, Any]]] = {p: [] for p in range(1, dom.total_pages + 1)}
    for v in violations:
        p_idx = v.get("global_page_index", 1)
        page_violations.setdefault(p_idx, []).append(v)

    return page_nodes, page_violations


def _draw_single_node_overlay(
    node: DOMNode,
    active_viols: List[Dict[str, Any]],
    draw_base: ImageDraw.ImageDraw,
    draw_overlay: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    sx: float,
    sy: float
):
    """Renders visual overlay bounding box polygon and violation callout badge for a single node."""
    bbox = node.bounding_box
    x0, y0 = bbox.x0 * sx, bbox.y0 * sy
    x1, y1 = bbox.x1 * sx, bbox.y1 * sy

    if x1 <= x0:
        x1 = x0 + 20
    if y1 <= y0:
        y1 = y0 + 15

    palette = COLOR_PALETTE.get(node.type, COLOR_PALETTE["paragraph"])
    stroke_col = palette["stroke"]
    has_violation = len(active_viols) > 0
    width_val = 4 if has_violation else 3

    if has_violation:
        stroke_col = "#FF1744"

    if bbox.angle != 0.0:
        polygon = bbox.to_polygon(sx=sx, sy=sy)
        draw_overlay.polygon(polygon, outline=stroke_col, width=width_val)
    else:
        draw_overlay.rectangle([x0, y0, x1, y1], outline=stroke_col, width=width_val)

    label_text = f"[{node.type}] {node.node_id}"
    left, top, right, bottom = font.getbbox(label_text)
    text_w, text_h = right - left, bottom - top

    badge_x0 = x0
    badge_y0 = max(0, y0 - text_h - 4)
    badge_x1 = badge_x0 + text_w + 8
    badge_y1 = badge_y0 + text_h + 4

    draw_base.rectangle([badge_x0, badge_y0, badge_x1, badge_y1], fill=stroke_col)
    draw_base.text((badge_x0 + 4, badge_y0 + 2), label_text, fill="white", font=font)

    if has_violation:
        draw_violation_callout(draw_base, x0, badge_y1, active_viols[0], font)


def _draw_top_banner_summary(
    draw_result: ImageDraw.ImageDraw, img_w: int, page_no: int, nodes_count: int, violations_count: int, header_font: ImageFont.ImageFont
):
    """Renders top banner summary bar across image width."""
    banner_h = 32
    draw_result.rectangle([0, 0, img_w, banner_h], fill="#1E1E2F")
    draw_result.text(
        (12, 6),
        f"cernodata Visual Provenance Overlay | Page {page_no} | Nodes: {nodes_count} | Violations: {violations_count}",
        fill="#FF5252" if violations_count > 0 else "#00E676",
        font=header_font
    )


class PageVisualizer:
    """
    Renders PDF page overlays with parsed DOM bounding box annotations, rotated text alignment polygons,
    and quality violation markers.
    """

    def __init__(self, dpi: int = 150):
        self.dpi = dpi
        self.scale = dpi / 72.0  # PDF points to pixel scale factor

    def render_overlay(
        self,
        pdf_path: str,
        dom: DocumentDOM,
        violations: Optional[List[Dict[str, Any]]] = None,
        output_dir: str = "output",
        decision: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        os.makedirs(output_dir, exist_ok=True)
        output_paths = []
        violations = violations or []

        page_nodes, page_violations = _group_by_page(dom, violations)
        per_page = decision.get("per_page_confidence", {}) if decision else {}

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
                    p_conf = per_page.get(str(page_no), per_page.get(page_no))
                    if p_conf is None and decision:
                        p_conf = decision.get("overall_confidence")

                    overlay_img = self._draw_nodes_on_image(
                        pil_img, page_no, page_w, page_h, nodes_for_page, viols_for_page, confidence_score=p_conf
                    )
                    
                    out_path = os.path.join(output_dir, f"overlay_page_{page_no}.png")
                    overlay_img.save(out_path)
                    output_paths.append(out_path)
                return output_paths
            except Exception as e:
                print(f"[WARN] pypdfium2 rendering failed ({e}), using synthetic visualizer fallback.")

        for page_no, nodes_for_page in page_nodes.items():
            canvas_w, canvas_h = int(612 * self.scale), int(792 * self.scale)
            pil_img = Image.new("RGBA", (canvas_w, canvas_h), (245, 247, 250, 255))
            viols_for_page = page_violations.get(page_no, [])
            p_conf = per_page.get(str(page_no), per_page.get(page_no))
            if p_conf is None and decision:
                p_conf = decision.get("overall_confidence")
            overlay_img = self._draw_nodes_on_image(
                pil_img, page_no, 612.0, 792.0, nodes_for_page, viols_for_page, confidence_score=p_conf
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
        violations: List[Dict[str, Any]],
        confidence_score: Optional[float] = None
    ) -> Image.Image:
        img_w, img_h = base_img.size
        sx = img_w / page_w if page_w > 0 else self.scale
        sy = img_h / page_h if page_h > 0 else self.scale

        overlay = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        draw_base = ImageDraw.Draw(base_img)

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
            active_viols = node_violations.get(node.node_id, [])
            _draw_single_node_overlay(node, active_viols, draw_base, draw_overlay, font, sx, sy)

        result_img = Image.alpha_composite(base_img, overlay).convert("RGB")
        draw_result = ImageDraw.Draw(result_img)

        _draw_top_banner_summary(draw_result, img_w, page_no, len(nodes), len(violations), header_font)
        draw_score_badge_bottom_left(
            draw_result, img_w, img_h, page_no, nodes, violations, font, header_font, confidence_score=confidence_score
        )

        return result_img
