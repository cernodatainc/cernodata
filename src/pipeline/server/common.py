"""
src/pipeline/server/common.py

Shared utilities, constants, HTTP payload serialization, run discovery, and artifact loaders.
"""

from __future__ import annotations

import base64
import glob
import json
import logging
import os
import re
from http.server import SimpleHTTPRequestHandler
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

logger = logging.getLogger("cernodata.server.common")

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_ROOT = os.path.dirname(SRC_DIR)


def send_response_bytes(
    handler: SimpleHTTPRequestHandler,
    body: bytes,
    content_type: str,
    status_code: int = 200,
) -> bool:
    """Sends raw bytes response with specified Content-Type and Content-Length headers."""
    try:
        handler.send_response(status_code)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return True
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        logger.debug("Client disconnected before response could be sent: %s", e)
        return True


def send_json_response(handler: SimpleHTTPRequestHandler, status_code: int, payload: Any) -> None:
    """Sends JSON response with Content-Type and Content-Length headers."""
    body = json.dumps(payload).encode("utf-8")
    send_response_bytes(handler, body, content_type="application/json; charset=utf-8", status_code=status_code)


def read_json_payload(handler: SimpleHTTPRequestHandler) -> Dict[str, Any]:
    """Reads and decodes JSON request payload from HTTP request body."""
    try:
        content_length = int(handler.headers.get("Content-Length", 0))
    except (ValueError, TypeError):
        return {}
    if content_length <= 0:
        return {}
    try:
        body = handler.rfile.read(content_length).decode("utf-8")
        parsed = json.loads(body) if body else {}
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Malformed JSON request payload received: %s", e)
        return {}
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        logger.debug("Client disconnected while reading request payload: %s", e)
        return {}


def send_text_response(
    handler: SimpleHTTPRequestHandler,
    content: Union[str, bytes],
    content_type: str = "text/html; charset=utf-8",
    status_code: int = 200,
) -> None:
    """Sends text/script/HTML response with specified Content-Type and Content-Length headers."""
    body = content.encode("utf-8") if isinstance(content, str) else content
    send_response_bytes(handler, body, content_type=content_type, status_code=status_code)


def send_html_response(handler: SimpleHTTPRequestHandler, content: Union[str, bytes], status_code: int = 200) -> None:
    """Sends HTML response with Content-Type and Content-Length headers."""
    send_text_response(handler, content, content_type="text/html; charset=utf-8", status_code=status_code)


def send_file_response(
    handler: SimpleHTTPRequestHandler,
    file_path: str,
    content_type: str,
    status_code: int = 200,
) -> bool:
    """
    Sends file contents with specified Content-Type.
    Returns True if file exists and was sent, False if file was not found.
    """
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        return send_response_bytes(handler, content, content_type=content_type, status_code=status_code)
    except OSError as e:
        logger.warning("Error reading file %s: %s", file_path, e)
        return False


def send_first_existing_file(
    handler: SimpleHTTPRequestHandler,
    candidate_paths: Sequence[str],
    content_type: str,
    status_code: int = 200,
) -> bool:
    """Sends the first existing file among candidate paths, returning True if sent."""
    for path in candidate_paths:
        if path and send_file_response(handler, path, content_type=content_type, status_code=status_code):
            return True
    return False


def copy_file_if_exists(src_path: str, dst_path: str) -> bool:
    """Copies file from src_path to dst_path if src_path exists on disk."""
    if not os.path.exists(src_path):
        return False
    try:
        with open(src_path, "rb") as f_in:
            data = f_in.read()
        with open(dst_path, "wb") as f_out:
            f_out.write(data)
        return True
    except OSError as e:
        logger.warning("Could not copy asset from %s to %s: %s", src_path, dst_path, e)
        return False


def read_html_template(filename: str, fallback_title: str = "cernodata") -> str:
    """Reads HTML template file from src/visualization or returns fallback placeholder."""
    src_path = os.path.join(SRC_DIR, "visualization", filename)
    if os.path.exists(src_path):
        try:
            with open(src_path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            logger.warning("Could not read template %s: %s", src_path, e)
    return f"<html><body><h1>{fallback_title}</h1><p>Template missing.</p></body></html>"


def safe_load_json(file_path: str, default: Any = None) -> Any:
    """Safely reads and deserializes a JSON file if it exists, returning default on failure."""
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        logger.debug("Failed reading JSON file %s: %s", file_path, e)
        return default


def normalize_violations(raw_violations: Any) -> List[Dict[str, Any]]:
    """Normalizes violations data structure into a list of violation dictionaries."""
    if isinstance(raw_violations, list):
        return raw_violations
    if isinstance(raw_violations, dict):
        violations = raw_violations.get("violations", [])
        if isinstance(violations, list):
            return violations
    return []


def _extract_decision_from_html(html_path: str) -> Optional[Dict[str, Any]]:
    """Extracts embedded decision JSON object from interactive viewer HTML."""
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


def load_run_artifacts(run_dir: str) -> Dict[str, Any]:
    """
    Loads and coalesces pipeline execution artifacts from an output directory.
    Returns structured dictionary containing plan, decision, dom, violations, and metadata.
    """
    plan_res_path = os.path.join(run_dir, "plan_execution_result.json")
    plan_res_data: Dict[str, Any] = safe_load_json(plan_res_path, {})
    plan_data: Optional[Dict[str, Any]] = plan_res_data.get("plan") or safe_load_json(os.path.join(run_dir, "plan.json"))
    decision_data: Dict[str, Any] = (
        plan_res_data.get("decision")
        or safe_load_json(os.path.join(run_dir, "decision_tree.json"), {})
    )
    dom_data: Dict[str, Any] = safe_load_json(os.path.join(run_dir, "document_dom.json"), {})
    raw_viols = plan_res_data.get("violations")
    if raw_viols is None:
        raw_viols = safe_load_json(os.path.join(run_dir, "quality_violations.json"), [])
    violations = normalize_violations(raw_viols)

    html_path = os.path.join(run_dir, "interactive_viewer.html")
    html_decision = _extract_decision_from_html(html_path)
    if html_decision:
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
    """Constructs a standardized preset attempt record dictionary."""
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
) -> Dict[str, Any]:
    """Constructs the canonical dictionary structure required to hydrate interactive visual viewer."""
    det_langs = decision.get("detected_languages") if isinstance(decision, dict) else None
    dataset: Dict[str, Any] = {
        "dom": dom,
        "violations": violations,
        "decision": decision,
        "detectedLanguages": det_langs if isinstance(det_langs, dict) else {},
        "plan": plan,
        "pdfSourceFile": pdf_path,
        "activeLanguage": language,
        "pageImages": page_images,
        "pageDimensions": page_dimensions,
        "totalPages": total_pages,
        "outputDir": output_dir or "output",
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
    """Calculates pipeline milestone step index (1-5) based on progress percentage."""
    if pct >= 85:
        return 5
    if pct >= 65:
        return 4
    if pct >= 50:
        return 3
    if pct >= 30:
        return 2
    return 1


def find_previous_runs(repo_root: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Discovers completed output directories containing pipeline execution results,
    plans, DOM structures, or quality violation logs.
    """
    root = repo_root or REPO_ROOT
    patterns = [
        os.path.join(root, "output"),
        os.path.join(root, "output", "*"),
        os.path.join(root, "src", "output"),
        os.path.join(root, "src", "output", "*"),
        os.path.join(root, "src", "e2e", "output"),
        os.path.join(root, "src", "e2e", "output_*"),
        os.path.join(root, "output_*"),
    ]
    seen_dirs: Set[str] = set()
    runs: List[Dict[str, Any]] = []

    for pattern in patterns:
        for match in glob.glob(pattern):
            if not os.path.isdir(match):
                continue
            norm_rel = os.path.relpath(match, root).replace("\\", "/")
            if norm_rel in seen_dirs:
                continue

            try:
                files = os.listdir(match)
            except OSError:
                continue

            has_artifacts = any(
                f in files
                for f in (
                    "plan_execution_result.json",
                    "document_dom.json",
                    "plan.json",
                    "interactive_viewer.html",
                    "quality_violations.json",
                )
            )
            if not has_artifacts:
                continue

            seen_dirs.add(norm_rel)

            artifacts = load_run_artifacts(match)
            plan_data = artifacts["plan"]
            dom_data = artifacts["dom"]
            violations = artifacts["violations"]
            chosen_preset = artifacts["chosen_preset"]
            status = artifacts["status"]
            overall_confidence = artifacts["overall_confidence"]
            doc_name = artifacts["document_name"]
            doc_path = artifacts["document_path"]
            timestamp = plan_data.get("created_at", "") if plan_data else ""
            violations_count = len(violations)

            score_str = f"{overall_confidence:.4f}" if overall_confidence is not None else "1.0000"
            label = f"{doc_name} [{chosen_preset} | {status} {score_str} | {violations_count} viols] ({norm_rel})"

            total_pages = int(dom_data.get("total_pages", 1) or 1)
            decision_data = artifacts.get("decision", {})
            per_page_conf = decision_data.get("per_page_confidence", {})

            per_page_viols: Dict[str, int] = {}
            for v in violations:
                p_num = str(v.get("global_page_index") or v.get("page") or 1)
                per_page_viols[p_num] = per_page_viols.get(p_num, 0) + 1

            per_page_nodes: Dict[str, int] = {}
            for n in dom_data.get("nodes", []):
                p_num = str(n.get("global_page_index") or n.get("temp_slice_index") or 1)
                per_page_nodes[p_num] = per_page_nodes.get(p_num, 0) + 1

            attempts = decision_data.get("attempts", [])
            if attempts and len(attempts) > 1:
                for att in attempts:
                    att_preset = att.get("preset", chosen_preset)
                    att_conf = att.get("overall_confidence", overall_confidence)
                    att_status = att.get("status", status)
                    att_viols = att.get("violations_count", violations_count)
                    att_page_conf = att.get("per_page_confidence", per_page_conf)
                    att_step = att.get("step", 1)
                    att_id = f"{norm_rel}:step_{att_step}"
                    conf_str = f"{float(att_conf):.4f}" if att_conf is not None else "1.0000"
                    att_label = f"{doc_name} [{att_preset} (Step {att_step}) | {att_status} {conf_str} | {att_viols} viols] ({norm_rel})"

                    runs.append({
                        "id": att_id,
                        "dir_path": norm_rel,
                        "document_name": doc_name,
                        "document_path": doc_path,
                        "chosen_preset": att_preset,
                        "status": att_status,
                        "overall_confidence": att_conf if att_conf is not None else 1.0,
                        "violations_count": att_viols,
                        "timestamp": timestamp,
                        "has_viewer": os.path.exists(os.path.join(match, "interactive_viewer.html")),
                        "has_dom": bool(dom_data),
                        "has_plan": plan_data is not None,
                        "total_pages": total_pages,
                        "per_page_confidence": att_page_conf,
                        "per_page_violations": per_page_viols,
                        "per_page_nodes": per_page_nodes,
                        "label": att_label,
                    })
            else:
                runs.append({
                    "id": norm_rel,
                    "dir_path": norm_rel,
                    "document_name": doc_name,
                    "document_path": doc_path,
                    "chosen_preset": chosen_preset,
                    "status": status,
                    "overall_confidence": overall_confidence if overall_confidence is not None else 1.0,
                    "violations_count": violations_count,
                    "timestamp": timestamp,
                    "has_viewer": os.path.exists(os.path.join(match, "interactive_viewer.html")),
                    "has_dom": bool(dom_data),
                    "has_plan": plan_data is not None,
                    "total_pages": total_pages,
                    "per_page_confidence": per_page_conf,
                    "per_page_violations": per_page_viols,
                    "per_page_nodes": per_page_nodes,
                    "label": label,
                })

    runs.sort(key=lambda r: (r["dir_path"] != "output", r["dir_path"]))
    return runs


def build_runs_grid(runs: List[Dict[str, Any]], target_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Builds a table grid structure of previous runs for a given file.
    Horizontal axis: page numbers (1..max_pages).
    Vertical axis: parsing run identifiers (run_id / preset).
    """
    available_files: List[str] = sorted(list({
        str(r.get("document_name")) for r in runs if r.get("document_name")
    }))

    selected_file = target_file
    if not selected_file or selected_file not in available_files:
        selected_file = available_files[0] if available_files else ""

    file_runs = [r for r in runs if r.get("document_name") == selected_file] if selected_file else list(runs)

    # Determine maximum page count across all runs for this file
    max_pages = 1
    for r in file_runs:
        max_pages = max(max_pages, int(r.get("total_pages", 1) or 1))
        for p_key in r.get("per_page_confidence", {}).keys():
            try:
                max_pages = max(max_pages, int(p_key))
            except (ValueError, TypeError):
                pass
        for p_key in r.get("per_page_violations", {}).keys():
            try:
                max_pages = max(max_pages, int(p_key))
            except (ValueError, TypeError):
                pass

    pages = list(range(1, max_pages + 1))

    matrix_rows: List[Dict[str, Any]] = []
    for r in file_runs:
        pages_data: Dict[str, Dict[str, Any]] = {}
        for p in pages:
            p_str = str(p)
            conf = r.get("per_page_confidence", {}).get(p_str)
            if conf is None:
                conf = r.get("per_page_confidence", {}).get(p)
            viols = r.get("per_page_violations", {}).get(p_str, 0)
            nodes = r.get("per_page_nodes", {}).get(p_str, 0)
            pages_data[p_str] = {
                "page": p,
                "confidence": conf,
                "violations_count": viols,
                "nodes_count": nodes,
                "is_passed": (conf is not None and conf >= 0.85) if conf is not None else (r.get("status") == "ACCEPT"),
            }

        matrix_rows.append({
            "run_id": r.get("id", r.get("dir_path", "output")),
            "dir_path": r.get("dir_path", "output"),
            "preset": r.get("chosen_preset", "docling_fast"),
            "status": r.get("status", "ACCEPT"),
            "overall_confidence": r.get("overall_confidence", 1.0),
            "violations_count": r.get("violations_count", 0),
            "timestamp": r.get("timestamp", ""),
            "pages_data": pages_data,
        })

    return {
        "selected_file": selected_file,
        "available_files": available_files,
        "pages": pages,
        "runs": matrix_rows,
    }
