"""
src/pipeline/server/session.py

Thread-safe state container for server sessions, progress tracking, and hydration data.
"""

from __future__ import annotations

import base64
import glob
import json
import logging
import os
import threading
from typing import Any, Dict, List, Mapping, Optional

from src.pipeline.planner_models import DocumentPlan
from src.pipeline.server.common import REPO_ROOT, SRC_DIR, find_previous_runs
from src.utils import resolve_pdf_path

logger = logging.getLogger("cernodata.server.session")


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
                    f"[INFO] DOM Nodes: {len(dom_dict.get('nodes', []))}, Quality Violations: {len(viol_list)}.",
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
        log: Optional[str] = None,
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
            v_list = (
                raw_viols
                if isinstance(raw_viols, list)
                else (raw_viols.get("violations", []) if isinstance(raw_viols, dict) else [])
            )
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
                "nodes": [],
            }
            violations_data: List[Dict[str, Any]] = []
            decision_data: Dict[str, Any] = {
                "chosen_preset": "docling_fast",
                "overall_confidence": 1.0,
                "status": "ACCEPT",
                "attempts": list(self.preset_attempts),
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

            raw_pdf = (
                self.pdf_path
                or dom_data.get("source_filename")
                or (plan_data.get("document_path") if plan_data else None)
                or "src/e2e/Document 8.pdf"
            )
            pdf_path = resolve_pdf_path(raw_pdf)
            total_pages = dom_data.get("total_pages", 1) or 1

            from src.visualization.viewer.pdf_renderer import (
                get_pdf_page_dimensions,
                render_all_pages_to_base64,
            )

            page_images: List[str] = []
            page_dimensions: List[Dict[str, float]] = []

            if os.path.exists(pdf_path):
                try:
                    page_images = render_all_pages_to_base64(pdf_path, total_pages=total_pages)
                    page_dimensions = get_pdf_page_dimensions(pdf_path)
                except Exception as e:
                    logger.warning("Could not render page images for %s: %s", pdf_path, e)

            if not page_images:
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
            violations_list = (
                raw_v
                if isinstance(raw_v, list)
                else (raw_v.get("violations", []) if isinstance(raw_v, dict) else [])
            )
            total_pages = dom_dict.get("total_pages", 1) or 1

            from src.visualization.viewer.pdf_renderer import (
                get_pdf_page_dimensions,
                render_all_pages_to_base64,
            )

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
                existing_idx = next(
                    (i for i, a in enumerate(self.preset_attempts) if a.get("preset") == preset_name),
                    -1,
                )
                if existing_idx != -1:
                    self.preset_attempts[existing_idx] = record
                else:
                    self.preset_attempts.append(record)
