"""
src/pipeline/postprocessors/uncovered_region_detector.py

Default-on DOM postprocessor that scans rendered page images for visual regions
showing contrast variation and foreground ink density outside any detected DOMNode,
runs targeted section OCR on those regions, and inserts postprocessed DOMNodes.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from src.dom import BoundingBox, DOMNode, DOMNodeOrigin, DOMNodeType, DocumentDOM
from src.parsers.pdf_utils import HAS_PYPDFIUM, open_pdf
from src.parsers.section_ocr import SectionOCRParser, get_default_section_parser
from src.pipeline.postprocessors.base import PostprocessActionRecord
from src.quality.handlers import make_node_violation

logger = logging.getLogger("cernodata.pipeline.postprocessors.uncovered_region_detector")

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


@dataclass
class UncoveredRegionCandidate:
    """Candidate page region exhibiting uncovered contrast variation and ink density."""

    bounding_box: BoundingBox
    pixel_box: Tuple[int, int, int, int]
    contrast_std: float
    ink_density: float


def _to_rgb_and_gray(image_input: Any) -> Tuple[np.ndarray, np.ndarray]:
    """Converts a PIL Image or NumPy array into uint8 RGB and 2D grayscale arrays."""
    if isinstance(image_input, Image.Image):
        rgb = np.array(image_input.convert("RGB"), dtype=np.uint8)
    else:
        arr = np.asarray(image_input)
        if arr.ndim < 2 or arr.size == 0:
            empty = np.zeros((0, 0), dtype=np.uint8)
            return np.zeros((0, 0, 3), dtype=np.uint8), empty
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        if arr.ndim == 2:
            rgb = np.stack([arr, arr, arr], axis=-1)
        elif arr.ndim == 3 and arr.shape[2] == 1:
            g = arr[:, :, 0]
            rgb = np.stack([g, g, g], axis=-1)
        else:
            rgb = arr[:, :, :3]

    gray = np.dot(rgb[:, :, :3].astype(np.float32), [0.299, 0.587, 0.114]).astype(np.uint8)
    return rgb, gray


def _find_large_false_runs(mask_1d: np.ndarray, min_gap: int) -> List[Tuple[int, int]]:
    """Returns inclusive-exclusive [start, end) spans around True segments separated by >= min_gap."""
    indices = np.flatnonzero(mask_1d)
    if indices.size == 0:
        return []
    spans: List[Tuple[int, int]] = []
    start = int(indices[0])
    prev = int(indices[0])
    for idx_val in indices[1:]:
        idx = int(idx_val)
        if idx - prev > min_gap:
            spans.append((start, prev + 1))
            start = idx
        prev = idx
    spans.append((start, prev + 1))
    return spans


def _split_fg_xy_cut(
    fg_mask: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    gap_x: int,
    gap_y: int,
) -> List[Tuple[int, int, int, int]]:
    """Recursively segments a boolean foreground mask into bounding boxes via XY-cut gaps."""
    sub = fg_mask[y0:y1, x0:x1]
    ys = np.flatnonzero(sub.any(axis=1))
    xs = np.flatnonzero(sub.any(axis=0))
    if ys.size == 0 or xs.size == 0:
        return []

    nx0 = x0 + int(xs[0])
    nx1 = x0 + int(xs[-1]) + 1
    ny0 = y0 + int(ys[0])
    ny1 = y0 + int(ys[-1]) + 1
    tight = fg_mask[ny0:ny1, nx0:nx1]

    y_spans = _find_large_false_runs(tight.any(axis=1), gap_y)
    if len(y_spans) > 1:
        boxes: List[Tuple[int, int, int, int]] = []
        for sy0, sy1 in y_spans:
            boxes.extend(_split_fg_xy_cut(fg_mask, nx0, ny0 + sy0, nx1, ny0 + sy1, gap_x, gap_y))
        return boxes

    x_spans = _find_large_false_runs(tight.any(axis=0), gap_x)
    if len(x_spans) > 1:
        boxes = []
        for sx0, sx1 in x_spans:
            boxes.extend(_split_fg_xy_cut(fg_mask, nx0 + sx0, ny0, nx0 + sx1, ny1, gap_x, gap_y))
        return boxes

    return [(nx0, ny0, nx1, ny1)]


def _extract_candidate_pixel_boxes(
    ink_mask: np.ndarray,
    kernel_w: int,
    kernel_h: int,
) -> List[Tuple[int, int, int, int]]:
    """Groups foreground pixels into rectangular candidate pixel boxes."""
    if HAS_CV2:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, kernel_w), max(3, kernel_h)))
        dilated = cv2.dilate(ink_mask, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes: List[Tuple[int, int, int, int]] = []
        for contour in contours:
            rx, ry, rw, rh = cv2.boundingRect(contour)
            if rw > 0 and rh > 0:
                boxes.append((int(rx), int(ry), int(rx + rw), int(ry + rh)))
        return boxes

    h, w = ink_mask.shape[:2]
    return _split_fg_xy_cut(ink_mask > 0, 0, 0, w, h, max(3, kernel_w), max(3, kernel_h))


def detect_uncovered_regions_on_page(
    page_image_rgb: Any,
    existing_boxes: Sequence[BoundingBox],
    page_width_pt: float = 612.0,
    page_height_pt: float = 792.0,
    contrast_std_threshold: float = 18.0,
    ink_threshold: int = 200,
    min_ink_density: float = 0.015,
    max_ink_density: float = 0.85,
    min_region_width_pt: float = 20.0,
    min_region_height_pt: float = 8.0,
    max_overlap_ratio: float = 0.15,
    page_margin_pt: float = 12.0,
) -> List[UncoveredRegionCandidate]:
    """Detects visual regions with contrast variation and ink outside existing DOM nodes."""
    _rgb, gray = _to_rgb_and_gray(page_image_rgb)
    if gray.ndim != 2 or gray.size == 0 or page_width_pt <= 0.0 or page_height_pt <= 0.0:
        return []

    img_h, img_w = gray.shape
    scale_x = img_w / page_width_pt
    scale_y = img_h / page_height_pt

    masked_gray = gray.copy()
    margin_px_x = max(0, min(img_w // 4, int(round(page_margin_pt * scale_x))))
    margin_px_y = max(0, min(img_h // 4, int(round(page_margin_pt * scale_y))))
    if margin_px_y > 0:
        masked_gray[:margin_px_y, :] = 255
        masked_gray[img_h - margin_px_y :, :] = 255
    if margin_px_x > 0:
        masked_gray[:, :margin_px_x] = 255
        masked_gray[:, img_w - margin_px_x :] = 255

    pad_px = 2
    for bbox in existing_boxes:
        bx0 = max(0, int(np.floor(bbox.x0 * scale_x)) - pad_px)
        by0 = max(0, int(np.floor(bbox.y0 * scale_y)) - pad_px)
        bx1 = min(img_w, int(np.ceil(bbox.x1 * scale_x)) + pad_px)
        by1 = min(img_h, int(np.ceil(bbox.y1 * scale_y)) + pad_px)
        if bx1 > bx0 and by1 > by0:
            masked_gray[by0:by1, bx0:bx1] = 255

    ink_mask = (masked_gray < ink_threshold).astype(np.uint8) * 255
    if not np.any(ink_mask):
        return []

    kernel_w = max(4, int(round(12.0 * scale_x)))
    kernel_h = max(3, int(round(6.0 * scale_y)))
    raw_boxes = _extract_candidate_pixel_boxes(ink_mask, kernel_w=kernel_w, kernel_h=kernel_h)

    candidates: List[UncoveredRegionCandidate] = []
    for rx0, ry0, rx1, ry1 in raw_boxes:
        sub_mask = ink_mask[ry0:ry1, rx0:rx1]
        active_y, active_x = np.nonzero(sub_mask)
        if active_y.size == 0 or active_x.size == 0:
            continue

        px0 = rx0 + int(active_x.min())
        px1 = rx0 + int(active_x.max()) + 1
        py0 = ry0 + int(active_y.min())
        py1 = ry0 + int(active_y.max()) + 1

        candidate_bbox = BoundingBox(
            x0=round(px0 / scale_x, 2),
            y0=round(py0 / scale_y, 2),
            x1=round(px1 / scale_x, 2),
            y1=round(py1 / scale_y, 2),
        )
        if candidate_bbox.width < min_region_width_pt or candidate_bbox.height < min_region_height_pt:
            continue
        if candidate_bbox.area <= 0.0:
            continue

        max_overlap = 0.0
        for ex_box in existing_boxes:
            inter = candidate_bbox.intersection(ex_box)
            if inter is not None and inter.area > 0.0:
                ratio = inter.area / candidate_bbox.area
                if ratio > max_overlap:
                    max_overlap = ratio
        if max_overlap > max_overlap_ratio:
            continue

        crop_gray = masked_gray[py0:py1, px0:px1]
        contrast_std = float(np.std(crop_gray))
        ink_density = float(np.mean(crop_gray < ink_threshold))
        if contrast_std < contrast_std_threshold:
            continue
        if ink_density < min_ink_density or ink_density > max_ink_density:
            continue

        candidates.append(
            UncoveredRegionCandidate(
                bounding_box=candidate_bbox,
                pixel_box=(px0, py0, px1, py1),
                contrast_std=contrast_std,
                ink_density=ink_density,
            )
        )

    candidates.sort(key=lambda c: (c.bounding_box.y0, c.bounding_box.x0))
    return candidates


def _unpack_page_image_entry(
    entry: Any, default_w: float = 612.0, default_h: float = 792.0
) -> Optional[Tuple[np.ndarray, float, float]]:
    """Normalizes a supplied page image entry to (rgb_array, page_width_pt, page_height_pt)."""
    if isinstance(entry, tuple) and len(entry) >= 3:
        rgb, _ = _to_rgb_and_gray(entry[0])
        return (rgb, float(entry[1]), float(entry[2])) if rgb.size > 0 else None
    rgb, _ = _to_rgb_and_gray(entry)
    if rgb.size == 0:
        return None
    return rgb, default_w, default_h


class UncoveredRegionPostprocessor:
    """Default-on postprocessor that recovers uncovered visual page regions via image analysis and OCR."""

    name: str = "uncovered_region_detector"

    def __init__(
        self,
        pdf_path: Optional[str] = None,
        page_images: Optional[Dict[int, Any]] = None,
        ocr_parser: Optional[SectionOCRParser] = None,
        ocr_engine: str = "rapidocr",
        language: Optional[str] = "en",
        render_scale: float = 150.0 / 72.0,
        contrast_std_threshold: float = 18.0,
        ink_threshold: int = 200,
        min_ink_density: float = 0.015,
        max_ink_density: float = 0.85,
        min_region_width_pt: float = 20.0,
        min_region_height_pt: float = 8.0,
        max_overlap_ratio: float = 0.15,
        page_margin_pt: float = 12.0,
        max_regions_per_page: int = 12,
    ) -> None:
        self.pdf_path = pdf_path
        self.page_images = page_images
        self.ocr_parser = ocr_parser
        self.ocr_engine = ocr_engine
        self.language = language
        self.render_scale = render_scale
        self.contrast_std_threshold = contrast_std_threshold
        self.ink_threshold = ink_threshold
        self.min_ink_density = min_ink_density
        self.max_ink_density = max_ink_density
        self.min_region_width_pt = min_region_width_pt
        self.min_region_height_pt = min_region_height_pt
        self.max_overlap_ratio = max_overlap_ratio
        self.page_margin_pt = page_margin_pt
        self.max_regions_per_page = max_regions_per_page

    def _resolve_page_images(self, dom: DocumentDOM) -> Dict[int, Tuple[np.ndarray, float, float]]:
        """Loads RGB page bitmaps and PDF page sizes from supplied images or PDF on disk."""
        resolved: Dict[int, Tuple[np.ndarray, float, float]] = {}
        supplied = self.page_images if self.page_images is not None else dom.metadata.get("page_images")
        page_dims = dom.metadata.get("page_dimensions", {})
        if isinstance(supplied, dict) and supplied:
            for raw_page_no, entry in supplied.items():
                page_no = int(raw_page_no)
                dim_info = page_dims.get(str(page_no)) or page_dims.get(page_no) or {}
                dw = float(dim_info.get("width", 612.0)) if isinstance(dim_info, dict) else 612.0
                dh = float(dim_info.get("height", 792.0)) if isinstance(dim_info, dict) else 792.0
                unpacked = _unpack_page_image_entry(entry, default_w=dw, default_h=dh)
                if unpacked is not None:
                    resolved[page_no] = unpacked
            return resolved

        target_pdf = self.pdf_path or dom.metadata.get("pdf_path") or dom.source_filename
        if not HAS_PYPDFIUM or not target_pdf or not isinstance(target_pdf, str) or not os.path.isfile(target_pdf):
            return resolved

        with open_pdf(target_pdf) as pdf:
            if pdf is None:
                logger.warning("Failed to open PDF for uncovered region postprocessing: %s", target_pdf)
                return resolved
            page_count = min(len(pdf), max(1, int(dom.total_pages or len(pdf))))
            for page_idx in range(page_count):
                page_no = page_idx + 1
                pdf_page = pdf[page_idx]
                page_w, page_h = pdf_page.get_size()
                try:
                    img_np = np.array(pdf_page.render(scale=self.render_scale).to_pil().convert("RGB"), dtype=np.uint8)
                    resolved[page_no] = (img_np, float(page_w), float(page_h))
                except Exception as exc:
                    logger.warning("Failed to render page %s for uncovered region detection: %s", page_no, exc)
        return resolved

    def _run_region_ocr(self, crop_rgb: np.ndarray) -> Tuple[str, float]:
        """Runs targeted OCR on a cropped visual region and returns (text, confidence)."""
        parser = self.ocr_parser if self.ocr_parser is not None else get_default_section_parser()
        pil_crop = Image.fromarray(crop_rgb)
        try:
            ocr_res = parser.parse_image(
                pil_crop,
                language=self.language,
                engine_name=self.ocr_engine,
            )
        except Exception as exc:
            logger.debug("Targeted OCR failed on uncovered region crop: %s", exc)
            return "", 0.0

        if not isinstance(ocr_res, dict) or not ocr_res.get("success"):
            return "", 0.0
        text = str(ocr_res.get("text", "")).strip()
        conf = float(ocr_res.get("confidence", 0.0) or 0.0)
        return text, round(conf, 4)

    def _next_node_id(self, dom: DocumentDOM, page_no: int, seq_start: int) -> str:
        """Generates a unique DOMNode identifier for a newly recovered uncovered region."""
        seq = seq_start
        candidate_id = f"node_p{page_no}_post_uncovered_{seq}"
        while dom.get_node_by_id(candidate_id) is not None:
            seq += 1
            candidate_id = f"node_p{page_no}_post_uncovered_{seq}"
        return candidate_id

    def process(self, dom: DocumentDOM) -> Tuple[DocumentDOM, List[PostprocessActionRecord]]:
        """Scans pages for uncovered visual regions, runs targeted OCR, and appends postprocessed DOMNodes."""
        images_by_page = self._resolve_page_images(dom)
        if not images_by_page:
            return dom, []

        records: List[PostprocessActionRecord] = []
        for page_no in sorted(images_by_page.keys()):
            rgb_arr, page_w, page_h = images_by_page[page_no]
            existing_boxes = [n.bounding_box for n in dom.get_nodes_by_page(page_no)]
            candidates = detect_uncovered_regions_on_page(
                rgb_arr,
                existing_boxes,
                page_width_pt=page_w,
                page_height_pt=page_h,
                contrast_std_threshold=self.contrast_std_threshold,
                ink_threshold=self.ink_threshold,
                min_ink_density=self.min_ink_density,
                max_ink_density=self.max_ink_density,
                min_region_width_pt=self.min_region_width_pt,
                min_region_height_pt=self.min_region_height_pt,
                max_overlap_ratio=self.max_overlap_ratio,
                page_margin_pt=self.page_margin_pt,
            )
            if self.max_regions_per_page > 0 and len(candidates) > self.max_regions_per_page:
                candidates = sorted(candidates, key=lambda c: c.bounding_box.area, reverse=True)[
                    : self.max_regions_per_page
                ]
                candidates.sort(key=lambda c: (c.bounding_box.y0, c.bounding_box.x0))

            for seq_idx, cand in enumerate(candidates, start=1):
                px0, py0, px1, py1 = cand.pixel_box
                crop_rgb = rgb_arr[py0:py1, px0:px1]
                ocr_text, ocr_conf = self._run_region_ocr(crop_rgb)
                node_id = self._next_node_id(dom, page_no, seq_idx)

                content: Dict[str, Any] = {
                    "raw_text": ocr_text,
                    "origin": DOMNodeOrigin.POSTPROCESSED.value,
                    "source": self.name,
                    "postprocessor": self.name,
                    "contrast_std": round(cand.contrast_std, 2),
                    "ink_density": round(cand.ink_density, 4),
                }
                new_node = DOMNode(
                    node_id=node_id,
                    type=DOMNodeType.PARAGRAPH.value,
                    global_page_index=page_no,
                    temp_slice_index=page_no,
                    bounding_box=cand.bounding_box,
                    content=content,
                    ocr_confidence=ocr_conf,
                    is_incorrect_text=True if not ocr_text else None,
                    origin=DOMNodeOrigin.POSTPROCESSED.value,
                )

                if not ocr_text:
                    reason = (
                        f"Uncovered visual contrast region (std={cand.contrast_std:.1f}, "
                        f"ink={cand.ink_density:.1%}) detected with empty OCR output"
                    )
                    new_node.add_violation(
                        make_node_violation(
                            node=new_node,
                            counter=len(records) + 1,
                            v_type="structure",
                            rule_type="uncovered_visual_region",
                            severity="WARNING",
                            description=f"{reason}; manual review recommended",
                        )
                    )
                else:
                    reason = (
                        f"Recovered uncovered visual region via {self.ocr_engine} "
                        f"(std={cand.contrast_std:.1f}, ink={cand.ink_density:.1%})"
                    )

                dom.add_node(new_node)
                records.append(
                    PostprocessActionRecord(
                        step_name=self.name,
                        action="added_node",
                        node_id=node_id,
                        page_index=page_no,
                        reason=reason,
                        original_node_dict=new_node.to_dict(),
                    )
                )

        if records:
            dom.sort_nodes(by_reading_order=True)
        return dom, records
