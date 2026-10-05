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
from http.server import SimpleHTTPRequestHandler
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cernodata.server.common")

SRC_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO_ROOT = os.path.dirname(SRC_DIR)


def send_json_response(handler: SimpleHTTPRequestHandler, status_code: int, payload: Any) -> None:
    """Sends JSON response with Content-Type and Content-Length headers."""
    try:
        body = json.dumps(payload).encode("utf-8")
        handler.send_response(status_code)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        logger.debug("Client disconnected before JSON response could be sent: %s", e)


def read_json_payload(handler: SimpleHTTPRequestHandler) -> Dict[str, Any]:
    """Reads and decodes JSON request payload from HTTP request body."""
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length <= 0:
        return {}
    try:
        body = handler.rfile.read(content_length).decode("utf-8")
        return json.loads(body) if body else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Malformed JSON request payload received: %s", e)
        return {}
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        logger.debug("Client disconnected while reading request payload: %s", e)
        return {}


def send_text_response(
    handler: SimpleHTTPRequestHandler,
    content: str | bytes,
    content_type: str = "text/html; charset=utf-8",
    status_code: int = 200,
) -> None:
    """Sends text/script/HTML response with specified Content-Type and Content-Length headers."""
    try:
        body = content.encode("utf-8") if isinstance(content, str) else content
        handler.send_response(status_code)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        logger.debug("Client disconnected before response could be sent: %s", e)


def send_html_response(handler: SimpleHTTPRequestHandler, content: str | bytes, status_code: int = 200) -> None:
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
        handler.send_response(status_code)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Content-Length", str(len(content)))
        handler.end_headers()
        handler.wfile.write(content)
        return True
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
        logger.debug("Client disconnected while sending file %s: %s", file_path, e)
        return True
    except OSError as e:
        logger.warning("Error reading file %s: %s", file_path, e)
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


def load_run_artifacts(run_dir: str) -> Dict[str, Any]:
    """
    Loads and coalesces pipeline execution artifacts from an output directory.
    Returns structured dictionary containing plan, decision, dom, violations, and metadata.
    """
    plan_res_data: Dict[str, Any] = safe_load_json(os.path.join(run_dir, "plan_execution_result.json"), {})
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

    if os.path.exists(pdf_path):
        try:
            from src.visualization.viewer.pdf_renderer import (
                get_pdf_page_dimensions,
                render_all_pages_to_base64,
            )

            page_images = render_all_pages_to_base64(pdf_path, total_pages=total_pages)
            page_dimensions = get_pdf_page_dimensions(pdf_path)
        except Exception as e:
            logger.warning("Could not render page images for %s: %s", pdf_path, e)

    if not page_images:
        for p in range(1, total_pages + 1):
            img_candidate = os.path.join(target_dir, f"overlay_page_{p}.png")
            if os.path.exists(img_candidate):
                try:
                    with open(img_candidate, "rb") as img_f:
                        b64 = base64.b64encode(img_f.read()).decode("ascii")
                        page_images.append(f"data:image/png;base64,{b64}")
                        if len(page_dimensions) < p:
                            page_dimensions.append({"width": 612.0, "height": 792.0})
                except Exception as e:
                    logger.warning("Could not load overlay image %s: %s", img_candidate, e)

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
    seen_dirs: set[str] = set()
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
                "label": label,
            })

    runs.sort(key=lambda r: (r["dir_path"] != "output", r["dir_path"]))
    return runs
