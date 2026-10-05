"""
src/pipeline/server.py

Zero-dependency HTTP server and live pipeline hub for interactive web application.
Serves thin landing page with navigation to input selection, planning, watching progress,
and multi-preset comparison results. Serves clean viewer HTML and JS assets and hydrates
runtime data from backend /api/viewer_data endpoint instead of returning templated HTML.
Provides multi-threaded execution and thread-safe session tracking.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import sys
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Any, List, Optional, Mapping, Tuple
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("cernodata.server")

from src.utils import mkdirs, find_available_port, resolve_pdf_path
from src.parsers.section_ocr import parse_image_ocr, parse_section_from_pdf
from src.pipeline.planner_options import (
    DEFAULT_PRESET_WEIGHTS,
    TAXONOMY_OPTIONS,
    TARGET_OPTIONS,
    SECURITY_OPTIONS,
    WIZARD_DIMENSIONS,
)
from src.pipeline.planner_models import DocumentPlan, PlannerCriteria

SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


class ServerSessionContext:
    """Thread-safe state container for server sessions, progress tracking, and hydration data."""

    def __init__(
        self,
        pdf_path: str = "",
        language: str = "en",
        repo_root: Optional[str] = None,
        src_dir: Optional[str] = None,
        output_dir: str = "output",
    ) -> None:
        self._lock = threading.RLock()
        self.pdf_path: str = pdf_path
        self.language: str = language
        self.repo_root: str = repo_root or REPO_ROOT
        self.src_dir: str = src_dir or SRC_DIR
        self.output_dir: str = output_dir.replace("\\", "/")
        self.viewer_data: Optional[Dict[str, Any]] = None
        self.current_result: Optional[Dict[str, Any]] = None
        self.preset_attempts: List[Dict[str, Any]] = []
        self.submitted_plan: Optional[DocumentPlan] = None
        self.progress_state: Dict[str, Any] = {
            "status": "idle",
            "progress": 0,
            "step_index": 0,
            "current_step": "Idle - ready to execute",
            "logs": ["[INIT] Server ready. Waiting to trigger pipeline."],
            "completed": False,
            "error": None,
        }

    def get_available_documents(self) -> List[str]:
        """Finds candidate PDF documents in repository."""
        docs: List[str] = []
        patterns = [
            os.path.join(self.repo_root, "src", "e2e", "*.pdf"),
            os.path.join(self.repo_root, "output", "*.pdf"),
            os.path.join(self.repo_root, "*.pdf"),
            os.path.join(self.src_dir, "e2e", "*.pdf"),
        ]
        for pattern in patterns:
            for match in glob.glob(pattern):
                try:
                    rel = os.path.relpath(match, self.repo_root).replace("\\", "/")
                except Exception:
                    rel = match.replace("\\", "/")
                if rel not in docs:
                    docs.append(rel)
        with self._lock:
            if not docs and self.pdf_path:
                docs.append(self.pdf_path)
        return docs

    def get_previous_runs(self) -> List[Dict[str, Any]]:
        """Finds completed output runs available in repository."""
        return find_previous_runs(self.repo_root)

    def load_previous_run(self, output_dir: str) -> Dict[str, Any]:
        """Loads artifacts from an output directory into session state."""
        with self._lock:
            norm_rel = output_dir.replace("\\", "/").strip()
            self.output_dir = norm_rel
            full_dir = norm_rel if os.path.isabs(norm_rel) else os.path.join(self.repo_root, norm_rel)
            if not os.path.exists(full_dir):
                logger.warning("Requested output directory does not exist: %s", full_dir)
                return {}

            plan_res_path = os.path.join(full_dir, "plan_execution_result.json")
            plan_path = os.path.join(full_dir, "plan.json")
            dom_path = os.path.join(full_dir, "document_dom.json")
            viol_path = os.path.join(full_dir, "quality_violations.json")
            dec_path = os.path.join(full_dir, "decision_tree.json")

            plan_dict: Optional[Dict[str, Any]] = None
            decision_dict: Dict[str, Any] = {}
            dom_dict: Dict[str, Any] = {}
            viol_list: List[Dict[str, Any]] = []

            if os.path.exists(plan_res_path):
                try:
                    with open(plan_res_path, "r", encoding="utf-8") as f:
                        res_data = json.load(f)
                        decision_dict = res_data.get("decision", {})
                        plan_dict = res_data.get("plan")
                except Exception as e:
                    logger.warning("Error loading %s: %s", plan_res_path, e)

            if os.path.exists(plan_path) and not plan_dict:
                try:
                    with open(plan_path, "r", encoding="utf-8") as f:
                        plan_dict = json.load(f)
                except Exception as e:
                    logger.warning("Error loading %s: %s", plan_path, e)

            if os.path.exists(dec_path) and not decision_dict:
                try:
                    with open(dec_path, "r", encoding="utf-8") as f:
                        decision_dict = json.load(f)
                except Exception as e:
                    logger.warning("Error loading %s: %s", dec_path, e)

            if os.path.exists(dom_path):
                try:
                    with open(dom_path, "r", encoding="utf-8") as f:
                        dom_dict = json.load(f)
                except Exception as e:
                    logger.warning("Error loading %s: %s", dom_path, e)

            if os.path.exists(viol_path):
                try:
                    with open(viol_path, "r", encoding="utf-8") as f:
                        loaded_viols = json.load(f)
                        if isinstance(loaded_viols, list):
                            viol_list = loaded_viols
                        elif isinstance(loaded_viols, dict):
                            viol_list = loaded_viols.get("violations", [])
                except Exception as e:
                    logger.warning("Error loading %s: %s", viol_path, e)

            if plan_dict:
                try:
                    self.submitted_plan = DocumentPlan.from_dict(plan_dict)
                    if self.submitted_plan.document_path:
                        self.pdf_path = resolve_pdf_path(self.submitted_plan.document_path)
                    if self.submitted_plan.language:
                        self.language = self.submitted_plan.language
                except Exception as e:
                    logger.warning("Could not parse DocumentPlan from %s: %s", norm_rel, e)
            elif dom_dict.get("source_filename"):
                self.pdf_path = resolve_pdf_path(dom_dict["source_filename"])

            if not decision_dict and dom_dict:
                decision_dict = {
                    "chosen_preset": "docling_fast",
                    "overall_confidence": 1.0,
                    "status": "ACCEPT",
                }

            if decision_dict.get("language") and not self.language:
                self.language = decision_dict["language"]

            attempts = decision_dict.get("attempts", [])
            if attempts:
                self.preset_attempts = list(attempts)
            elif decision_dict:
                chosen_preset = decision_dict.get("chosen_preset", "docling_fast")
                self.preset_attempts = [{
                    "step": 1,
                    "preset": chosen_preset,
                    "overall_confidence": decision_dict.get("overall_confidence", 1.0),
                    "per_page_confidence": decision_dict.get("per_page_confidence", {}),
                    "violations_count": len(viol_list),
                    "status": decision_dict.get("status", "ACCEPT"),
                    "is_accepted": decision_dict.get("is_accepted", True),
                    "action": decision_dict.get("decision_tree", {}).get("action", "ACCEPT_OUTPUT"),
                }]

            self.current_result = {
                "decision": decision_dict,
                "violations": viol_list,
                "plan": plan_dict,
                "dom": dom_dict,
            }
            # Invalidate cached viewer_data so it rehydrates from the newly loaded run
            self.viewer_data = None

            conf_val = decision_dict.get("overall_confidence", 1.0)
            status_val = decision_dict.get("status", "ACCEPT")
            chosen_preset = decision_dict.get("chosen_preset", "docling_fast")

            self.progress_state = {
                "status": "completed",
                "progress": 100,
                "step_index": 5,
                "current_step": f"Loaded Previous Run ({status_val})",
                "logs": [
                    f"[LOAD] Successfully loaded previous run artifacts from '{self.output_dir}'.",
                    f"[INFO] Document: '{self.pdf_path or dom_dict.get('source_filename', 'N/A')}', Chosen Preset: '{chosen_preset}', Confidence: {conf_val}, Status: '{status_val}'.",
                    f"[INFO] DOM Nodes: {len(dom_dict.get('nodes', []))}, Quality Violations: {len(viol_list)}."
                ],
                "completed": True,
                "error": None,
            }

            return {
                "output_dir": self.output_dir,
                "document_path": self.pdf_path,
                "decision": decision_dict,
                "plan": plan_dict,
                "violations_count": len(viol_list),
                "attempts": list(self.preset_attempts),
            }

    def get_progress(self) -> Dict[str, Any]:
        """Thread-safe retrieval of current progress state."""
        with self._lock:
            state = dict(self.progress_state)
            state["logs"] = list(self.progress_state.get("logs", []))
            return state

    def update_progress(
        self,
        progress: int,
        step_index: int,
        current_step: str,
        log: Optional[str] = None,
        status: str = "running",
        completed: bool = False,
        error: Optional[str] = None,
    ) -> None:
        """Thread-safe update of progress state and log history."""
        with self._lock:
            self.progress_state["progress"] = progress
            self.progress_state["step_index"] = step_index
            self.progress_state["current_step"] = current_step
            self.progress_state["status"] = status
            self.progress_state["completed"] = completed
            if error is not None:
                self.progress_state["error"] = error
            if log:
                self.progress_state.setdefault("logs", []).append(log)

    def add_log(self, message: str) -> None:
        """Thread-safe appending of a log message."""
        with self._lock:
            self.progress_state.setdefault("logs", []).append(message)

    def reset_progress(self, initial_step: str = "Starting...", log: Optional[str] = None) -> None:
        """Thread-safe reset of progress state to initiate a new run."""
        with self._lock:
            logs: List[str] = []
            if log:
                logs.append(log)
            self.progress_state = {
                "status": "running",
                "progress": 10,
                "step_index": 1,
                "current_step": initial_step,
                "logs": logs,
                "completed": False,
                "error": None,
            }

    def set_error(self, error_msg: str, log: Optional[str] = None) -> None:
        """Thread-safe recording of an execution error."""
        with self._lock:
            self.progress_state["status"] = "error"
            self.progress_state["error"] = error_msg
            self.progress_state["completed"] = False
            if log:
                self.progress_state.setdefault("logs", []).append(log)

    def set_completed(
        self,
        status: str,
        confidence: float,
        violations_count: int,
        log: Optional[str] = None
    ) -> None:
        """Thread-safe recording of a successful pipeline run completion."""
        with self._lock:
            self.progress_state["status"] = "completed"
            self.progress_state["completed"] = True
            self.progress_state["progress"] = 100
            self.progress_state["step_index"] = 5
            self.progress_state["current_step"] = f"Step 5: Decision Tree Complete ({status})"
            if log:
                self.progress_state.setdefault("logs", []).append(log)

    def get_results(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Thread-safe retrieval of preset comparison results."""
        with self._lock:
            if output_dir and output_dir != self.output_dir:
                self.load_previous_run(output_dir)
            elif not self.preset_attempts and not self.current_result:
                self.load_previous_run(self.output_dir or "output")
            raw_viols = self.current_result.get("violations") if self.current_result else []
            v_list = raw_viols if isinstance(raw_viols, list) else (raw_viols.get("violations", []) if isinstance(raw_viols, dict) else [])
            return {
                "attempts": list(self.preset_attempts),
                "decision": self.current_result.get("decision") if self.current_result else None,
                "violations": v_list,
                "output_dir": self.output_dir or "output",
            }

    def get_viewer_data(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Thread-safe retrieval and hydration of viewer state."""
        with self._lock:
            if output_dir and output_dir != self.output_dir:
                self.load_previous_run(output_dir)

            if self.viewer_data is not None:
                return self.viewer_data

            target_dir = self.output_dir or "output"
            target_full = target_dir if os.path.isabs(target_dir) else os.path.join(self.repo_root, target_dir)

            dom_file = os.path.join(target_full, "document_dom.json")
            viol_file = os.path.join(target_full, "quality_violations.json")
            dec_file = os.path.join(target_full, "decision_tree.json")
            plan_file = os.path.join(target_full, "plan.json")
            plan_res_file = os.path.join(target_full, "plan_execution_result.json")

            dom_data: Dict[str, Any] = {
                "document_id": "doc_init",
                "source_filename": self.pdf_path or "Document 8.pdf",
                "total_pages": 1,
                "nodes": []
            }
            violations_data: List[Dict[str, Any]] = []
            decision_data: Dict[str, Any] = {
                "chosen_preset": "docling_fast",
                "overall_confidence": 1.0,
                "status": "ACCEPT",
                "attempts": list(self.preset_attempts)
            }
            plan_data: Optional[Dict[str, Any]] = None

            if os.path.exists(plan_res_file):
                try:
                    with open(plan_res_file, "r", encoding="utf-8") as f:
                        res_obj = json.load(f)
                        if "decision" in res_obj:
                            decision_data = res_obj["decision"]
                        if "plan" in res_obj:
                            plan_data = res_obj["plan"]
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Could not load plan_execution_result from %s: %s", plan_res_file, e)

            if os.path.exists(dom_file):
                try:
                    with open(dom_file, "r", encoding="utf-8") as f:
                        dom_data = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Could not load DOM cache from %s: %s", dom_file, e)

            if os.path.exists(viol_file):
                try:
                    with open(viol_file, "r", encoding="utf-8") as f:
                        loaded_v = json.load(f)
                        if isinstance(loaded_v, list):
                            violations_data = loaded_v
                        elif isinstance(loaded_v, dict):
                            violations_data = loaded_v.get("violations", [])
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Could not load violations cache from %s: %s", viol_file, e)

            if os.path.exists(dec_file) and not decision_data.get("decision_tree"):
                try:
                    with open(dec_file, "r", encoding="utf-8") as f:
                        decision_data = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Could not load decision cache from %s: %s", dec_file, e)

            if os.path.exists(plan_file) and plan_data is None:
                try:
                    with open(plan_file, "r", encoding="utf-8") as f:
                        plan_data = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("Could not load plan cache from %s: %s", plan_file, e)

            raw_pdf = self.pdf_path or dom_data.get("source_filename") or (plan_data.get("document_path") if plan_data else None) or "src/e2e/Document 8.pdf"
            pdf_path = resolve_pdf_path(raw_pdf)
            total_pages = dom_data.get("total_pages", 1) or 1

            from src.visualization.viewer.pdf_renderer import render_all_pages_to_base64, get_pdf_page_dimensions
            page_images: List[str] = []
            page_dimensions: List[Dict[str, float]] = []

            if os.path.exists(pdf_path):
                try:
                    page_images = render_all_pages_to_base64(pdf_path, total_pages=total_pages)
                    page_dimensions = get_pdf_page_dimensions(pdf_path)
                except Exception as e:
                    logger.warning("Could not render page images for %s: %s", pdf_path, e)

            if not page_images:
                import base64
                for p in range(1, total_pages + 1):
                    img_candidate = os.path.join(target_full, f"overlay_page_{p}.png")
                    if os.path.exists(img_candidate):
                        try:
                            with open(img_candidate, "rb") as img_f:
                                b64 = base64.b64encode(img_f.read()).decode("ascii")
                                page_images.append(f"data:image/png;base64,{b64}")
                                if len(page_dimensions) < p:
                                    page_dimensions.append({"width": 612.0, "height": 792.0})
                        except Exception as e:
                            logger.warning("Could not load overlay image %s: %s", img_candidate, e)

            if not decision_data.get("attempts") and self.preset_attempts:
                decision_data["attempts"] = list(self.preset_attempts)

            self.viewer_data = {
                "dom": dom_data,
                "violations": violations_data,
                "decision": decision_data,
                "detectedLanguages": decision_data.get("detected_languages", {}),
                "plan": plan_data,
                "pdfSourceFile": pdf_path,
                "activeLanguage": self.language or decision_data.get("language", "en"),
                "pageImages": page_images,
                "pageDimensions": page_dimensions,
                "totalPages": total_pages,
                "outputDir": target_dir,
            }
            return self.viewer_data

    def update_result_state(self, result: Mapping[str, Any], pdf_path: str, language: str) -> None:
        """Thread-safe update of server result state and hydration dataset."""
        resolved_path = resolve_pdf_path(pdf_path)
        with self._lock:
            self.current_result = dict(result)
            self.pdf_path = resolved_path
            self.language = language

            dom_dict = result["dom"]
            decision_dict = result["decision"]
            raw_v = result.get("violations", [])
            violations_list = raw_v if isinstance(raw_v, list) else (raw_v.get("violations", []) if isinstance(raw_v, dict) else [])
            total_pages = dom_dict.get("total_pages", 1) or 1

            from src.visualization.viewer.pdf_renderer import render_all_pages_to_base64, get_pdf_page_dimensions
            page_images: List[str] = []
            page_dimensions: List[Dict[str, float]] = []

            if os.path.exists(resolved_path):
                try:
                    page_images = render_all_pages_to_base64(resolved_path, total_pages=total_pages)
                    page_dimensions = get_pdf_page_dimensions(resolved_path)
                except Exception as e:
                    logger.warning("Could not render page images for %s: %s", resolved_path, e)

            self.viewer_data = {
                "dom": dom_dict,
                "violations": violations_list,
                "decision": decision_dict,
                "detectedLanguages": decision_dict.get("detected_languages", {}),
                "plan": result.get("plan"),
                "pdfSourceFile": resolved_path,
                "activeLanguage": language,
                "pageImages": page_images,
                "pageDimensions": page_dimensions,
                "totalPages": total_pages,
            }

            # Sync preset attempts
            attempts = decision_dict.get("attempts", [])
            if attempts:
                self.preset_attempts = list(attempts)
            else:
                preset_name = decision_dict.get("chosen_preset", "docling_fast")
                record = {
                    "step": len(self.preset_attempts) + 1,
                    "preset": preset_name,
                    "overall_confidence": decision_dict.get("overall_confidence", 1.0),
                    "per_page_confidence": decision_dict.get("per_page_confidence", {}),
                    "violations_count": len(violations_list),
                    "status": decision_dict.get("status", "ACCEPT"),
                    "is_accepted": decision_dict.get("is_accepted", True),
                    "action": decision_dict.get("decision_tree", {}).get("action", "ACCEPT_PARSE"),
                }
                existing_idx = next((i for i, a in enumerate(self.preset_attempts) if a.get("preset") == preset_name), -1)
                if existing_idx != -1:
                    self.preset_attempts[existing_idx] = record
                else:
                    self.preset_attempts.append(record)


class PipelineViewerServer(ThreadingHTTPServer):
    """Multi-threaded HTTP server managing background pipeline executor and session context."""

    session_context: ServerSessionContext
    executor: ThreadPoolExecutor
    shutdown_on_submit: bool = False
    html_content: str = ""
    default_doc: Optional[str] = None
    default_lang: Optional[str] = None
    default_threshold: float = 0.85
    output_dir: str = "output"
    planner: Any = None

    def __init__(
        self,
        server_address: Tuple[str, int],
        RequestHandlerClass: type[SimpleHTTPRequestHandler],
        session_context: Optional[ServerSessionContext] = None,
        max_workers: int = 4,
    ) -> None:
        super().__init__(server_address, RequestHandlerClass)
        self.session_context = session_context or ServerSessionContext()
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cernodata-worker")

    @property
    def submitted_plan(self) -> Optional[DocumentPlan]:
        return self.session_context.submitted_plan

    @submitted_plan.setter
    def submitted_plan(self, value: Optional[DocumentPlan]) -> None:
        self.session_context.submitted_plan = value

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Suppresses tracebacks for normal client socket aborts and resets."""
        exc_type, exc_val, _ = sys.exc_info()
        if exc_type in (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            logger.debug("Client %s disconnected abruptly: %s", client_address, exc_val)
            return
        super().handle_error(request, client_address)

    def server_close(self) -> None:
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False, cancel_futures=True)
        super().server_close()


class PipelineViewerHandler(SimpleHTTPRequestHandler):
    """HTTP request handler serving landing page, viewer assets, hydration API, and execution endpoints."""

    def handle(self) -> None:
        """Handles request while catching normal client socket aborts."""
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
            logger.debug("Client disconnected during connection handling: %s", e)

    _default_session: ServerSessionContext = ServerSessionContext()
    _fallback_executor: Optional[ThreadPoolExecutor] = None

    pdf_path: str = ""
    language: str = "en"
    viewer_data: Optional[Dict[str, Any]] = None
    current_result: Optional[Dict[str, Any]] = None
    preset_attempts: List[Dict[str, Any]] = []
    progress_state: Dict[str, Any] = {
        "status": "idle",
        "progress": 0,
        "step_index": 0,
        "current_step": "Idle - ready to execute",
        "logs": ["[INIT] Server ready. Waiting to trigger pipeline."],
        "completed": False,
        "error": None,
    }

    @property
    def session(self) -> ServerSessionContext:
        """Returns the thread-safe session context attached to the server or default fallback."""
        if hasattr(self.server, "session_context") and self.server.session_context is not None:
            return self.server.session_context
        return self.__class__._default_session

    @property
    def executor(self) -> ThreadPoolExecutor:
        """Returns the thread pool executor attached to the server or creates a fallback."""
        if hasattr(self.server, "executor") and self.server.executor is not None:
            return self.server.executor
        if self.__class__._fallback_executor is None:
            self.__class__._fallback_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fallback-worker")
        return self.__class__._fallback_executor

    @classmethod
    def get_available_documents(cls) -> List[str]:
        """Finds candidate PDF documents in repository delegating to default session."""
        return cls._default_session.get_available_documents()

    @classmethod
    def get_previous_runs(cls) -> List[Dict[str, Any]]:
        """Returns discovered completed output directories delegating to default session."""
        return cls._default_session.get_previous_runs()

    @classmethod
    def load_previous_run(cls, output_dir: str) -> Dict[str, Any]:
        """Loads and switches default session to an existing output directory."""
        res = cls._default_session.load_previous_run(output_dir)
        cls.pdf_path = cls._default_session.pdf_path
        cls.language = cls._default_session.language
        cls.viewer_data = cls._default_session.viewer_data
        cls.current_result = cls._default_session.current_result
        cls.preset_attempts = cls._default_session.preset_attempts
        return res

    @classmethod
    def get_viewer_data(cls) -> Dict[str, Any]:
        """Returns structured data required to hydrate the interactive visual viewer."""
        return cls._default_session.get_viewer_data()

    @classmethod
    def update_result_state(cls, result: Mapping[str, Any], pdf_path: str, language: str) -> None:
        """Updates server memory state and hydration dataset from run_pipeline result."""
        cls._default_session.update_result_state(result, pdf_path, language)
        cls.pdf_path = cls._default_session.pdf_path
        cls.language = cls._default_session.language
        cls.viewer_data = cls._default_session.viewer_data
        cls.current_result = cls._default_session.current_result
        cls.preset_attempts = cls._default_session.preset_attempts

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        raw_path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # 1. Landing Page / Wizard Page
        if raw_path in ("", "/", "/index.html", "/landing", "/hub"):
            html_override = getattr(self.server, "html_content", "")
            if html_override:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_override.encode("utf-8"))
                return

            landing_path = os.path.join(SRC_DIR, "visualization", "landing.html")
            if os.path.exists(landing_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(landing_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(500, "Landing page template not found")
            return

        # 2. Viewer HTML (un-templated, dynamically hydrated)
        elif raw_path in ("/viewer", "/viewer.html"):
            viewer_file = os.path.join(SRC_DIR, "visualization", "viewer", "viewer.html")
            if not os.path.exists(viewer_file):
                viewer_file = os.path.join(SRC_DIR, "visualization", "viewer", "template.html")
            if os.path.exists(viewer_file):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(viewer_file, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(500, "Viewer template not found")
            return

        # 3. Interactive Viewer backwards compatibility
        elif raw_path == "/interactive_viewer.html":
            target_file = os.path.join(REPO_ROOT, self.session.output_dir or "output", "interactive_viewer.html")
            if not os.path.exists(target_file):
                target_file = os.path.join(REPO_ROOT, "output", "interactive_viewer.html")
            if os.path.exists(target_file):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(target_file, "rb") as f:
                    self.wfile.write(f.read())
                return
            viewer_file = os.path.join(SRC_DIR, "visualization", "viewer", "viewer.html")
            if os.path.exists(viewer_file):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(viewer_file, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "Interactive viewer not found")
            return

        # 4. Static CSS Asset
        elif raw_path == "/viewer.css":
            css_path = os.path.join(SRC_DIR, "visualization", "viewer", "viewer.css")
            if os.path.exists(css_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/css; charset=utf-8")
                self.end_headers()
                with open(css_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_error(404, "CSS asset not found")
            return

        # 5. Static JS Asset
        elif raw_path == "/viewer.js":
            from src.visualization.viewer.scripts import get_viewer_js
            js_content = get_viewer_js()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.end_headers()
            self.wfile.write(js_content.encode("utf-8"))
            return

        # 6. Planner / Data Shape Questionnaire
        elif raw_path in ("/data_shape_config.html", "/data_shape", "/planner"):
            html_override = getattr(self.server, "html_content", "")
            if html_override:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_override.encode("utf-8"))
                return

            candidate_paths = [
                os.path.join(REPO_ROOT, self.session.output_dir or "output", "data_shape_config.html"),
                os.path.join(REPO_ROOT, "output", "data_shape_config.html"),
                os.path.join(SRC_DIR, "visualization", "data_shape_config.html")
            ]
            for target_file in candidate_paths:
                if os.path.exists(target_file):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    with open(target_file, "rb") as f:
                        self.wfile.write(f.read())
                    return
            self.send_error(404, "Planner page not found")
            return

        # 7. API Endpoints
        elif raw_path == "/api/config":
            default_doc = getattr(self.server, "default_doc", None) or self.session.pdf_path or "src/e2e/Document 8.pdf"
            default_lang = getattr(self.server, "default_lang", None) or self.session.language or "en"
            default_thresh = getattr(self.server, "default_threshold", 0.85)

            send_json_response(self, 200, {
                "default_doc": default_doc,
                "default_lang": default_lang,
                "default_threshold": default_thresh,
                "preset_weights": DEFAULT_PRESET_WEIGHTS,
                "dimensions": [
                    {
                        "key": d.key,
                        "title": d.title,
                        "description": d.description,
                        "options": d.options,
                        "default": d.default,
                    }
                    for d in WIZARD_DIMENSIONS
                ],
                "taxonomy_options": TAXONOMY_OPTIONS,
                "target_options": TARGET_OPTIONS,
                "security_options": SECURITY_OPTIONS,
                "previous_runs": self.session.get_previous_runs(),
                "active_run": self.session.output_dir,
            })
            return

        elif raw_path in ("/api/previous_runs", "/api/runs"):
            send_json_response(self, 200, {
                "runs": self.session.get_previous_runs(),
                "active_run": self.session.output_dir,
            })
            return

        elif raw_path == "/api/load_run":
            target_dir = query_params.get("output_dir", [""])[0]
            if target_dir:
                loaded = self.session.load_previous_run(target_dir)
                send_json_response(self, 200, {
                    "success": True,
                    "output_dir": self.session.output_dir,
                    "run": loaded,
                    "results": self.session.get_results(),
                })
                return
            send_json_response(self, 400, {"success": False, "error": "Missing output_dir parameter"})
            return

        elif raw_path == "/api/documents":
            send_json_response(self, 200, {"documents": self.session.get_available_documents()})
            return

        elif raw_path == "/api/progress":
            send_json_response(self, 200, self.session.get_progress())
            return

        elif raw_path == "/api/results":
            res_target_dir: Optional[str] = query_params.get("output_dir", [""])[0] or None
            send_json_response(self, 200, self.session.get_results(output_dir=res_target_dir))
            return

        elif raw_path == "/api/viewer_data":
            v_target_dir: Optional[str] = query_params.get("output_dir", [""])[0] or None
            data = self.session.get_viewer_data(output_dir=v_target_dir)
            send_json_response(self, 200, data)
            return

        self.send_error(404, f"Endpoint not found: {raw_path}")

    def do_POST(self) -> None:
        payload = read_json_payload(self)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if self.path == "/api/load_run":
            target_dir = payload.get("output_dir") or payload.get("run_id") or "output"
            loaded = self.session.load_previous_run(target_dir)
            send_json_response(self, 200, {
                "success": True,
                "output_dir": self.session.output_dir,
                "run": loaded,
                "results": self.session.get_results(),
            })
            return

        if self.path == "/api/run":
            raw_pdf = payload.get("pdf_path", self.session.pdf_path) or "src/e2e/Document 8.pdf"
            pdf_path = resolve_pdf_path(raw_pdf)
            language = payload.get("language", self.session.language)
            threshold = float(payload.get("target_threshold", 0.85))
            preset = payload.get("preset", "docling_fast")
            align_skew = bool(payload.get("align_skew", True))
            visualize = bool(payload.get("visualize", True))
            with_plan = bool(payload.get("with_plan", False))
            plan_config = payload.get("plan_config")

            self.session.reset_progress(
                initial_step="Step 1: Document Validation & Subdivision",
                log=f"[{timestamp}] [START] Ingestion initiated for '{pdf_path}' (Preset: {preset}, Lang: {language}).",
            )
            self.session.add_log(f"[{timestamp}] [STEP 1] Validating document structure and parameters...")

            from src.pipeline.orchestrator import run_pipeline, PipelineExecutionResult
            from src.pipeline.planner import PresetPlanner

            plan_obj = None
            if with_plan and plan_config:
                planner = PresetPlanner()
                criteria = PlannerCriteria(
                    taxonomy=plan_config.get("taxonomy", "standard"),
                    target=plan_config.get("target_use_case", "rag_vector_search"),
                    security=plan_config.get("security", "air_gapped_local"),
                )
                plan_obj = planner.create_plan(
                    document_path=pdf_path,
                    criteria=criteria,
                    language=language,
                    target_threshold=threshold,
                )

            session = self.session

            def on_progress(pct: int, step_desc: str, log_msg: str) -> None:
                t = datetime.now().strftime("%H:%M:%S")
                step_idx = 1
                if pct >= 100:
                    step_idx = 5
                elif pct >= 85:
                    step_idx = 5
                elif pct >= 65:
                    step_idx = 4
                elif pct >= 50:
                    step_idx = 3
                elif pct >= 30:
                    step_idx = 2
                session.update_progress(
                    progress=pct,
                    step_index=step_idx,
                    current_step=step_desc,
                    log=f"[{t}] {log_msg}",
                )

            def _execute_run() -> PipelineExecutionResult:
                res = run_pipeline(
                    pdf_path=pdf_path,
                    target_threshold=threshold,
                    language=language,
                    preset=preset,
                    align_skew=align_skew,
                    visualize=visualize,
                    plan=plan_obj,
                    progress_callback=on_progress,
                )
                session.update_result_state(res, pdf_path=pdf_path, language=language)
                dec = res.get("decision", {})
                score = float(dec.get("overall_confidence", 1.0) or 1.0)
                status = str(dec.get("status", "ACCEPT"))
                t_end = datetime.now().strftime("%H:%M:%S")
                session.set_completed(
                    status=status,
                    confidence=score,
                    violations_count=len(res.get("violations", [])),
                    log=f"[{t_end}] [SUCCESS] Run complete: Status '{status}', Confidence: {score:.4f}, Violations: {len(res.get('violations', []))}."
                )
                return res

            try:
                future = self.executor.submit(_execute_run)
                result = future.result()

                send_json_response(self, 200, {
                    "success": True,
                    "preset": preset,
                    "language": language,
                    "dom": result["dom"],
                    "violations": result["violations"],
                    "decision": result["decision"],
                    "plan": result.get("plan"),
                })
                return
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                logger.info("Client disconnected before pipeline result could be returned.")
                return
            except Exception as e:
                t_err = datetime.now().strftime("%H:%M:%S")
                session.set_error(str(e), log=f"[{t_err}] [ERROR] Pipeline failure: {e}")
                send_json_response(self, 500, {"success": False, "error": str(e)})
                return

        elif self.path == "/api/rerun":
            preset = payload.get("preset", "docling_deep")
            raw_pdf = payload.get("pdf_path", self.session.pdf_path) or "src/e2e/Document 8.pdf"
            pdf_path = resolve_pdf_path(raw_pdf)
            language = payload.get("language", self.session.language)

            print(f"\n[SERVER API] Triggering live pipeline rerun for preset: '{preset}' (PDF: {pdf_path}, Lang: {language})...")
            from src.pipeline.orchestrator import run_pipeline, PipelineExecutionResult

            session = self.session

            def on_progress(pct: int, step_desc: str, log_msg: str) -> None:
                t = datetime.now().strftime("%H:%M:%S")
                step_idx = 2 if pct < 50 else (3 if pct < 70 else (4 if pct < 85 else 5))
                session.update_progress(
                    progress=pct,
                    step_index=step_idx,
                    current_step=step_desc,
                    log=f"[{t}] {log_msg}",
                )

            def _execute_rerun() -> PipelineExecutionResult:
                res = run_pipeline(
                    pdf_path=pdf_path,
                    preset=preset,
                    language=language,
                    progress_callback=on_progress,
                )
                session.update_result_state(res, pdf_path=pdf_path, language=language)
                return res

            try:
                future = self.executor.submit(_execute_rerun)
                result = future.result()
                send_json_response(self, 200, {
                    "success": True,
                    "preset": preset,
                    "language": language,
                    "dom": result["dom"],
                    "violations": result["violations"],
                    "decision": result["decision"]
                })
                return
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                logger.info("Client disconnected before rerun result could be returned.")
                return
            except Exception as e:
                send_json_response(self, 500, {"success": False, "error": str(e)})
                return

        elif self.path == "/api/calculate_scores":
            from src.pipeline.planner import PresetPlanner
            planner = getattr(self.server, "planner", None) or PresetPlanner()
            criteria = PlannerCriteria.from_dict(payload)
            scores = planner.calculate_scores(criteria=criteria)
            suggested = planner.suggest_preset_order(scores)

            send_json_response(self, 200, {
                "success": True,
                "scores": scores,
                "suggested_order": suggested,
            })
            return

        elif self.path == "/api/submit_plan":
            from src.pipeline.planner import PresetPlanner
            planner = getattr(self.server, "planner", None) or PresetPlanner()

            # Handle both raw DocumentPlan and questionnaire form submission
            if "primary_preset" in payload or ("target_threshold" in payload and "steps" in payload):
                from src.pipeline.planner_models import DocumentPlan
                plan = DocumentPlan.from_dict(payload)
                document_path = plan.document_path
            else:
                default_doc = getattr(self.server, "default_doc", None) or self.session.pdf_path
                document_path = payload.get("document_path", "").strip() or default_doc or ""
                criteria = PlannerCriteria.from_dict(payload)
                raw_lang = payload.get("language")
                language = raw_lang.strip() if (isinstance(raw_lang, str) and raw_lang.strip() and raw_lang.strip().lower() != "none") else None
                try:
                    default_thresh = getattr(self.server, "default_threshold", 0.82)
                    target_threshold = float(payload.get("target_threshold", default_thresh))
                except (ValueError, TypeError):
                    target_threshold = getattr(self.server, "default_threshold", 0.82)

                override_primary = payload.get("override_primary")
                override_order = payload.get("override_order")

                plan = planner.create_plan(
                    document_path=document_path,
                    criteria=criteria,
                    language=language,
                    target_threshold=target_threshold,
                    override_primary=override_primary,
                    override_order=override_order,
                )

            # Store plan in session context and server instance
            self.session.submitted_plan = plan
            setattr(self.server, "submitted_plan", plan)

            out_dir = getattr(self.server, "output_dir", None) or "output"
            if out_dir:
                mkdirs(out_dir)
                plan_file = os.path.join(out_dir, "plan.json")
                plan.save(plan_file)
            else:
                plan_file = ""

            resp_data: Dict[str, Any] = {
                "success": True,
                "plan_path": plan_file,
                "plan": plan.to_dict(),
            }
            if plan_file:
                resp_data["message"] = "Plan successfully configured and saved."
            else:
                resp_data["message"] = "Plan successfully configured but not saved (no output directory)."

            send_json_response(self, 200, resp_data)

            # In standalone wizard mode, shutdown server automatically on submission
            if getattr(self.server, "shutdown_on_submit", False):
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        elif self.path == "/api/save_dom":
            dom_data = payload.get("dom")
            output_dir = payload.get("output_dir", "output")

            if not dom_data:
                send_json_response(self, 400, {"error": "Missing dom payload"})
                return

            mkdirs(output_dir)
            dom_file = os.path.join(output_dir, "document_dom.json")
            with open(dom_file, "w", encoding="utf-8") as f:
                json.dump(dom_data, f, indent=2)

            print(f"\n[SERVER API] Saved updated DocumentDOM to '{dom_file}' ({len(dom_data.get('nodes', []))} nodes).")
            send_json_response(self, 200, {"success": True, "path": dom_file})
            return

        elif self.path in ("/api/parse_section_ocr", "/api/ocr_section"):
            node_id = payload.get("node_id", "")
            image_base64 = payload.get("image_base64")
            bbox = payload.get("bbox")
            page = int(payload.get("page", 1))
            pdf_path = payload.get("pdf_path", self.session.pdf_path)
            language = payload.get("language", self.session.language)

            print(f"\n[SERVER API] Parsing selected section '{node_id}' using OCR (Lang: {language})...")

            ocr_result: Any
            if image_base64:
                ocr_result = parse_image_ocr(image_base64, language=language)
            elif pdf_path and bbox:
                ocr_result = parse_section_from_pdf(pdf_path, page, bbox, language=language)
            else:
                send_json_response(self, 400, {
                    "success": False,
                    "error": "Either image_base64 or (pdf_path and bbox) must be provided."
                })
                return

            response_data = {
                "success": ocr_result.get("success", False),
                "node_id": node_id,
                "text": ocr_result.get("text", ""),
                "confidence": ocr_result.get("confidence", 0.0),
                "lines": ocr_result.get("lines", []),
                "error": ocr_result.get("error")
            }
            send_json_response(self, 200 if response_data["success"] else 422, response_data)
            return

        self.send_error(404, "Endpoint not found")


def serve_data_shape_wizard(
    planner: Any,
    default_doc: Optional[str] = None,
    default_lang: Optional[str] = None,
    default_threshold: float = 0.82,
    output_dir: str = "output",
    port: int = 8000,
    open_browser: bool = True
) -> DocumentPlan:
    """
    Serves interactive HTML questionnaire in browser to configure data shape parameters.
    Blocks until user submits plan via browser, then shuts down and returns DocumentPlan.
    """
    actual_port = find_available_port(start_port=port)

    # Locate and read HTML template
    html_src_path = os.path.join(SRC_DIR, "visualization", "data_shape_config.html")
    if os.path.exists(html_src_path):
        with open(html_src_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    else:
        html_content = "<html><body><h1>cernodata Data Shape Planner</h1><p>Template missing.</p></body></html>"

    # Also export standalone copy to output directory
    mkdirs(output_dir)
    exported_html_path = os.path.join(output_dir, "data_shape_config.html")
    with open(exported_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    session = ServerSessionContext(pdf_path=default_doc or "", language=default_lang or "en", output_dir=output_dir)
    httpd = PipelineViewerServer(("127.0.0.1", actual_port), PipelineViewerHandler, session_context=session)
    httpd.shutdown_on_submit = True
    httpd.planner = planner
    httpd.default_doc = default_doc
    httpd.default_lang = default_lang
    httpd.default_threshold = default_threshold
    httpd.output_dir = output_dir
    httpd.html_content = html_content

    url = f"http://127.0.0.1:{actual_port}/data_shape_config.html"

    print("=" * 68, flush=True)
    print("cernodata: Interactive Data Shape & Preset Planner", flush=True)
    print("=" * 68, flush=True)
    print(f"Serving data shape questionnaire at: {url}", flush=True)
    print("Awaiting configuration in browser... (Press Ctrl+C to abort)", flush=True)
    print("=" * 68, flush=True)

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        print("\n[SERVER] Data shape session interrupted by user.")
        httpd.server_close()
        raise

    httpd.server_close()

    if httpd.submitted_plan is not None:
        return httpd.submitted_plan

    # Fallback if somehow exited without plan
    return planner.create_plan(
        document_path=default_doc or "",
        language=default_lang,
        target_threshold=default_threshold
    )


def start_pipeline_server(
    pdf_path: str = "",
    language: str = "en",
    port: int = 8000,
    open_browser: bool = True
) -> None:
    """Starts local multi-threaded HTTP server and opens interactive hub landing page in default web browser."""
    actual_port = find_available_port(start_port=port)
    session = ServerSessionContext(pdf_path=pdf_path, language=language)
    PipelineViewerHandler._default_session = session

    server_address = ("", actual_port)
    httpd = PipelineViewerServer(server_address, PipelineViewerHandler, session_context=session)
    url = f"http://localhost:{actual_port}/"

    print("=" * 68)
    print(f"cernodata Ingestion Hub & Visual Server running at {url}")
    print(f"Dashboard Landing Page: {url}")
    print(f"Interactive Visual Flow Viewer: {url}viewer")
    print(f"Backend Hydration API: {url}api/viewer_data")
    print("=" * 68)

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Stopping pipeline server.")
        httpd.server_close()


def main() -> None:
    """CLI entrypoint for standalone pipeline server."""
    import argparse

    parser = argparse.ArgumentParser(
        description="cernodata: Document Ingestion Hub, Preset Planner and Interactive Visual Viewer Server."
    )
    parser.add_argument("--pdf", "--input", "-i", type=str, default="", help="Path to initial PDF document")
    parser.add_argument("--language", "-l", type=str, default="en", help="Default language hint code (e.g. 'pl', 'en')")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    args = parser.parse_args()

    start_pipeline_server(
        pdf_path=args.pdf,
        language=args.language,
        port=args.port,
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
