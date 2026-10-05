"""
src/pipeline/server/common.py

Shared utilities, constants, HTTP payload serialization, and run discovery.
"""

from __future__ import annotations

import glob
import json
import logging
import os
from http.server import SimpleHTTPRequestHandler
from typing import Any, Dict, List, Optional

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

            doc_name = "Unknown"
            doc_path = ""
            chosen_preset = "N/A"
            status = "ACCEPT"
            overall_confidence: Optional[float] = None
            violations_count = 0
            timestamp = ""
            plan_data: Optional[Dict[str, Any]] = None
            decision_data: Dict[str, Any] = {}

            plan_res_path = os.path.join(match, "plan_execution_result.json")
            if os.path.exists(plan_res_path):
                try:
                    with open(plan_res_path, "r", encoding="utf-8") as f:
                        res_data = json.load(f)
                        decision_data = res_data.get("decision", {})
                        chosen_preset = decision_data.get("chosen_preset") or res_data.get("chosen_preset", "N/A")
                        status = decision_data.get("status") or res_data.get("status", "ACCEPT")
                        overall_confidence = decision_data.get("overall_confidence")
                        violations_count = int(res_data.get("total_violations", 0))
                        plan_data = res_data.get("plan")
                except Exception as e:
                    logger.debug("Failed parsing %s: %s", plan_res_path, e)

            plan_path = os.path.join(match, "plan.json")
            if os.path.exists(plan_path) and not plan_data:
                try:
                    with open(plan_path, "r", encoding="utf-8") as f:
                        plan_data = json.load(f)
                except Exception as e:
                    logger.debug("Failed parsing %s: %s", plan_path, e)

            if plan_data:
                doc_path = plan_data.get("document_path", "")
                if chosen_preset == "N/A":
                    chosen_preset = plan_data.get("primary_preset", "N/A")
                timestamp = plan_data.get("created_at", "")

            dom_path = os.path.join(match, "document_dom.json")
            if os.path.exists(dom_path):
                try:
                    with open(dom_path, "r", encoding="utf-8") as f:
                        dom_data = json.load(f)
                        src_file = dom_data.get("source_filename")
                        if src_file:
                            if not doc_path:
                                doc_path = src_file
                            doc_name = os.path.basename(src_file)
                except Exception as e:
                    logger.debug("Failed parsing %s: %s", dom_path, e)

            viol_path = os.path.join(match, "quality_violations.json")
            if os.path.exists(viol_path) and violations_count == 0:
                try:
                    with open(viol_path, "r", encoding="utf-8") as f:
                        v_data = json.load(f)
                        if isinstance(v_data, list):
                            violations_count = len(v_data)
                        elif isinstance(v_data, dict):
                            violations_count = int(v_data.get("total_violations", len(v_data.get("violations", []))))
                except Exception as e:
                    logger.debug("Failed parsing %s: %s", viol_path, e)

            if doc_path and doc_name == "Unknown":
                doc_name = os.path.basename(doc_path)

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
                "has_dom": os.path.exists(dom_path),
                "has_plan": plan_data is not None,
                "label": label,
            })

    runs.sort(key=lambda r: (r["dir_path"] != "output", r["dir_path"]))
    return runs
