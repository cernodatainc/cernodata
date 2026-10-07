"""
src/pipeline/server/artifacts.py

Pipeline artifact loading, schema normalization, decision extraction,
and visual viewer dataset compilation for server consumption.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cernodata.server.artifacts")


def safe_load_json(file_path: str, default: Any = None) -> Any:
    """
    Safely reads and deserializes a JSON file if it exists.

    Args:
        file_path: Path to target JSON file.
        default: Fallback value returned if file is missing or invalid.

    Returns:
        Deserialized JSON object or specified default.
    """
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        logger.debug("Failed reading JSON file %s: %s", file_path, e)
        return default


def normalize_violations(raw_violations: Any) -> List[Dict[str, Any]]:
    """
    Normalizes arbitrary violations payloads into a standard list of violation mappings.

    Args:
        raw_violations: List or dictionary containing violation records.

    Returns:
        List of violation dictionaries.
    """
    if isinstance(raw_violations, list):
        return raw_violations
    if isinstance(raw_violations, dict):
        violations = raw_violations.get("violations", [])
        if isinstance(violations, list):
            return violations
    return []


def extract_decision_from_html(html_path: str) -> Optional[Dict[str, Any]]:
    """
    Extracts embedded decision JSON object from interactive viewer HTML file.

    Args:
        html_path: Path to interactive_viewer.html file.

    Returns:
        Parsed decision dictionary if found, or None.
    """
    if not os.path.exists(html_path):
        return None
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"decision:\s*(\{.*?\})\s*,\s*(?:detectedLanguages|violations):", content, re.DOTALL)
        if match:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
    except Exception as e:
        logger.debug("Could not extract decision from %s: %s", html_path, e)
    return None


# Backward compatibility alias
_extract_decision_from_html = extract_decision_from_html


def load_run_artifacts(run_dir: str) -> Dict[str, Any]:
    """
    Loads and coalesces pipeline execution artifacts from an output directory.

    Coalesces plan execution result, plan definition, decision tree evaluation,
    document DOM structure, and detected quality violations.

    Args:
        run_dir: Path to directory containing output artifacts.

    Returns:
        Dictionary mapping artifact identifiers to deserialized data.
    """
    plan_res_path = os.path.join(run_dir, "plan_execution_result.json")
    plan_res_data: Dict[str, Any] = safe_load_json(plan_res_path, {})
    plan_data: Optional[Dict[str, Any]] = plan_res_data.get("plan") or safe_load_json(os.path.join(run_dir, "plan.json"))
    dec_tree_path = os.path.join(run_dir, "decision_tree.json")
    saved_dec = safe_load_json(dec_tree_path, {})
    decision_data: Dict[str, Any] = saved_dec if saved_dec else (
        plan_res_data.get("decision") or {}
    )
    dom_data: Dict[str, Any] = safe_load_json(os.path.join(run_dir, "document_dom.json"), {})
    raw_dom_data: Dict[str, Any] = safe_load_json(os.path.join(run_dir, "raw_document_dom.json"), {}) or dom_data
    diff_data: Dict[str, Any] = safe_load_json(os.path.join(run_dir, "run_diff.json"), {})

    q_viols_path = os.path.join(run_dir, "quality_violations.json")
    saved_viols = safe_load_json(q_viols_path, None)
    raw_viols = saved_viols if saved_viols is not None else plan_res_data.get("violations", [])
    violations = normalize_violations(raw_viols)

    html_path = os.path.join(run_dir, "interactive_viewer.html")
    html_decision = extract_decision_from_html(html_path)
    if html_decision and not saved_dec:
        plan_mtime = os.path.getmtime(plan_res_path) if os.path.exists(plan_res_path) else 0.0
        html_mtime = os.path.getmtime(html_path)
        dec_page_count = len(decision_data.get("per_page_confidence", {})) if decision_data else 0
        html_page_count = len(html_decision.get("per_page_confidence", {}))

        # Favor HTML decision if plan_execution_result was missing, HTML is newer, or HTML has more page scores
        if not decision_data or html_mtime > plan_mtime or html_page_count > dec_page_count:
            decision_data = html_decision

    total_pages = int(dom_data.get("total_pages", 1) or 1)
    per_page_conf = dict(decision_data.get("per_page_confidence", {}))
    missing_pages = [p for p in range(1, total_pages + 1) if str(p) not in per_page_conf and p not in per_page_conf]

    if missing_pages and dom_data.get("nodes"):
        try:
            from src.dom import DocumentDOM
            from src.quality import evaluate_document_confidence
            temp_dom = DocumentDOM.from_dict(dom_data)
            metrics = evaluate_document_confidence(temp_dom, language=decision_data.get("language") or "en")
            for p, sc in metrics.get("per_page_confidence", {}).items():
                if str(p) not in per_page_conf and p not in per_page_conf:
                    per_page_conf[str(p)] = sc
            decision_data["per_page_confidence"] = per_page_conf
            if (decision_data.get("overall_confidence") == 1.0 or not decision_data.get("overall_confidence")) and violations:
                decision_data["overall_confidence"] = metrics.get("overall_confidence", 1.0)
        except Exception as e:
            logger.debug("Could not compute fallback per-page confidence: %s", e)

    chosen_preset = decision_data.get("chosen_preset") or plan_res_data.get("chosen_preset", "N/A")
    status = decision_data.get("status") or plan_res_data.get("status", "ACCEPT")
    overall_confidence = decision_data.get("overall_confidence")

    doc_path = ""
    if plan_data:
        doc_path = plan_data.get("document_path", "")
        if chosen_preset == "N/A":
            chosen_preset = plan_data.get("primary_preset", "N/A")

    if not doc_path and dom_data.get("source_filename"):
        doc_path = dom_data["source_filename"]

    doc_name = os.path.basename(doc_path) if doc_path else "Unknown"

    return {
        "plan_execution_result": plan_res_data,
        "plan": plan_data,
        "decision": decision_data,
        "dom": dom_data,
        "raw_dom": raw_dom_data,
        "diff": diff_data,
        "violations": violations,
        "chosen_preset": chosen_preset,
        "status": status,
        "overall_confidence": overall_confidence,
        "document_path": doc_path,
        "document_name": doc_name,
    }


def create_preset_attempt_record(
    decision_dict: Dict[str, Any],
    violations_count: int,
    step: int = 1,
    default_action: str = "ACCEPT_OUTPUT",
) -> Dict[str, Any]:
    """
    Constructs a standardized preset attempt record dictionary.

    Args:
        decision_dict: Evaluated decision tree output mapping.
        violations_count: Total detected quality violations count.
        step: Iteration index in execution attempt sequence.
        default_action: Default action identifier if decision_tree action is omitted.

    Returns:
        Structured attempt record dictionary.
    """
    preset_name = decision_dict.get("chosen_preset") or "docling_fast"
    tree = decision_dict.get("decision_tree")
    action = tree.get("action", default_action) if isinstance(tree, dict) else default_action
    conf = decision_dict.get("overall_confidence")
    overall_confidence = float(conf) if conf is not None else 1.0
    status = decision_dict.get("status") or "ACCEPT"
    per_page_conf = decision_dict.get("per_page_confidence")
    return {
        "step": step,
        "preset": preset_name,
        "overall_confidence": overall_confidence,
        "per_page_confidence": per_page_conf if isinstance(per_page_conf, dict) else {},
        "violations_count": violations_count,
        "status": status,
        "is_accepted": decision_dict.get("is_accepted", True),
        "action": action,
    }


def build_viewer_dataset(
    dom: Dict[str, Any],
    violations: List[Dict[str, Any]],
    decision: Dict[str, Any],
    plan: Optional[Dict[str, Any]],
    pdf_path: str,
    language: str,
    page_images: List[str],
    page_dimensions: List[Dict[str, float]],
    total_pages: int,
    output_dir: Optional[str] = None,
    raw_dom: Optional[Dict[str, Any]] = None,
    diff: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Constructs canonical dataset required to hydrate interactive visual viewer.
    Stores raw result and diff to eliminate expensive redundant preset reruns.
    """
    resolved_raw_dom = raw_dom if raw_dom is not None else dom
    resolved_diff = diff if diff is not None else {}
    resolved_output_dir = output_dir if output_dir else "output"

    det_langs = decision.get("detected_languages") if isinstance(decision, dict) else None
    detected_languages = det_langs if isinstance(det_langs, dict) else {}

    dataset: Dict[str, Any] = {
        "dom": dom,
        "raw_dom": resolved_raw_dom,
        "diff": resolved_diff,
        "violations": violations,
        "decision": decision,
        "detectedLanguages": detected_languages,
        "plan": plan,
        "pdfSourceFile": pdf_path,
        "activeLanguage": language,
        "pageImages": page_images,
        "pageDimensions": page_dimensions,
        "totalPages": total_pages,
        "outputDir": resolved_output_dir,
    }
    return dataset


def load_or_render_page_images(
    pdf_path: str,
    target_dir: str,
    total_pages: int,
) -> Tuple[List[str], List[Dict[str, float]]]:
    """
    Renders PDF pages to base64 images and gets dimensions, falling back
    to pre-rendered overlay image files if direct rendering fails or is unavailable.

    Args:
        pdf_path: Path to source PDF document.
        target_dir: Output directory containing cached overlay images.
        total_pages: Expected page count.

    Returns:
        Tuple of (page_images_base64_list, page_dimensions_list).
    """
    page_images: List[str] = []
    page_dimensions: List[Dict[str, float]] = []

    # 1. Direct rendering from PDF if it exists on disk
    if pdf_path and os.path.exists(pdf_path):
        try:
            from src.visualization.viewer.pdf_renderer import (
                get_pdf_page_dimensions,
                render_all_pages_to_base64,
            )

            page_images = render_all_pages_to_base64(pdf_path, total_pages=total_pages)
            page_dimensions = get_pdf_page_dimensions(pdf_path)
        except Exception as e:
            logger.warning("Could not render page images for %s: %s", pdf_path, e)

    # 2. If page dimensions still missing, inspect interactive_viewer.html in target_dir
    if not page_dimensions:
        viewer_html_path = os.path.join(target_dir, "interactive_viewer.html")
        if os.path.exists(viewer_html_path):
            try:
                with open(viewer_html_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                dim_match = re.search(r"pageDimensions:\s*(\[[^\]]*\])", html_content)
                if dim_match:
                    parsed_dims = json.loads(dim_match.group(1))
                    if isinstance(parsed_dims, list) and len(parsed_dims) > 0:
                        page_dimensions = parsed_dims
            except Exception as e:
                logger.debug("Could not parse pageDimensions from interactive_viewer.html: %s", e)

    # 3. Fall back to pre-rendered overlay images
    if not page_images:
        from PIL import Image

        for p in range(1, total_pages + 1):
            img_candidate = os.path.join(target_dir, f"overlay_page_{p}.png")
            if os.path.exists(img_candidate):
                try:
                    with open(img_candidate, "rb") as img_f:
                        b64 = base64.b64encode(img_f.read()).decode("ascii")
                        page_images.append(f"data:image/png;base64,{b64}")

                    if len(page_dimensions) < p:
                        with Image.open(img_candidate) as pil_img:
                            w_px, h_px = pil_img.size
                            # Default PageVisualizer scale is 150 DPI / 72.0 points
                            pt_w = round(w_px * 72.0 / 150.0, 2)
                            pt_h = round(h_px * 72.0 / 150.0, 2)
                            page_dimensions.append({"width": pt_w, "height": pt_h})
                except Exception as e:
                    logger.warning("Could not load overlay image %s: %s", img_candidate, e)

    # 4. Final safety fallback to standard A4 (595.28 x 841.89)
    while len(page_dimensions) < len(page_images):
        page_dimensions.append({"width": 595.28, "height": 841.89})

    return page_images, page_dimensions


def calculate_progress_step(pct: int) -> int:
    """
    Calculates pipeline milestone step index (1-5) based on progress percentage.

    Args:
        pct: Progress percentage between 0 and 100.

    Returns:
        Step index between 1 and 5.
    """
    if pct >= 85:
        return 5
    if pct >= 65:
        return 4
    if pct >= 50:
        return 3
    if pct >= 30:
        return 2
    return 1
