"""
src/pipeline/server/session.py

Thread-safe state container orchestrating server sessions, run artifacts,
and interactive visual viewer data.
"""

from __future__ import annotations

import glob
import logging
import os
import threading
from typing import Any, Callable, Dict, List, Mapping, Optional

from src.pipeline.planner_models import DocumentPlan
from src.pipeline.server.artifacts import (
    build_viewer_dataset,
    create_preset_attempt_record,
    load_or_render_page_images,
    load_run_artifacts,
    normalize_violations,
)
from src.pipeline.server.discovery import build_runs_grid, find_previous_runs
from src.pipeline.server.http_utils import REPO_ROOT, SRC_DIR
from src.pipeline.server.preset_cache import PresetCache
from src.pipeline.server.progress import ProgressTracker
from src.utils import resolve_pdf_path

logger = logging.getLogger("cernodata.server.session")


class ServerSessionContext:
    """
    Thread-safe state container orchestrating pipeline sessions, loaded execution runs,
    real-time progress monitoring, and interactive viewer data hydration.
    """

    def __init__(
        self,
        pdf_path: str = "",
        language: str = "en",
        repo_root: Optional[str] = None,
        src_dir: Optional[str] = None,
        output_dir: str = "output",
    ) -> None:
        self._lock: threading.RLock = threading.RLock()
        self.pdf_path: str = pdf_path
        self.language: str = language
        self.repo_root: str = repo_root or REPO_ROOT
        self.src_dir: str = src_dir or SRC_DIR
        self.output_dir: str = output_dir.replace("\\", "/")
        self.viewer_data: Optional[Dict[str, Any]] = None
        self.current_result: Optional[Dict[str, Any]] = None
        self.preset_attempts: List[Dict[str, Any]] = []
        self.submitted_plan: Optional[DocumentPlan] = None

        self._progress_tracker: ProgressTracker = ProgressTracker(lock=self._lock)
        self._preset_cache: PresetCache = PresetCache(lock=self._lock)

    @property
    def progress_state(self) -> Dict[str, Any]:
        """Provides direct access to the progress tracker's current state."""
        return self._progress_tracker.progress_state

    @progress_state.setter
    def progress_state(self, val: Dict[str, Any]) -> None:
        self._progress_tracker.progress_state = val

    @property
    def preset_results(self) -> Dict[str, Dict[str, Any]]:
        """Provides direct access to cached preset results dictionary."""
        return self._preset_cache.preset_results

    @preset_results.setter
    def preset_results(self, val: Dict[str, Dict[str, Any]]) -> None:
        self._preset_cache.preset_results = val

    def get_available_documents(self) -> List[str]:
        """
        Finds candidate PDF documents in repository workspace.

        Returns:
            List of repository-relative PDF file paths.
        """
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
        """
        Finds completed output runs available in repository.

        Returns:
            List of discovered run metadata dictionaries.
        """
        return find_previous_runs(self.repo_root)

    def load_previous_run(self, output_dir: str) -> Dict[str, Any]:
        """
        Loads artifacts from an output directory into active session state.

        Args:
            output_dir: Directory path relative to repo root or absolute path.

        Returns:
            Summary of loaded artifacts and run attributes.
        """
        with self._lock:
            norm_rel = output_dir.replace("\\", "/").strip()
            self.output_dir = norm_rel
            full_dir = norm_rel if os.path.isabs(norm_rel) else os.path.join(self.repo_root, norm_rel)
            if not os.path.exists(full_dir):
                logger.warning("Requested output directory does not exist: %s", full_dir)
                return {}

            artifacts = load_run_artifacts(full_dir)
            plan_dict = artifacts["plan"]
            decision_dict = artifacts["decision"]
            dom_dict = artifacts["dom"]
            viol_list = artifacts["violations"]

            candidate_pdf_names: List[str] = []
            if plan_dict:
                try:
                    self.submitted_plan = DocumentPlan.from_dict(plan_dict)
                    if self.submitted_plan.document_path:
                        candidate_pdf_names.append(str(self.submitted_plan.document_path))
                    if self.submitted_plan.language:
                        self.language = self.submitted_plan.language
                except Exception as e:
                    logger.warning("Could not parse DocumentPlan from %s: %s", norm_rel, e)

            if dom_dict.get("source_filename"):
                candidate_pdf_names.append(str(dom_dict["source_filename"]))

            found_pdf = False
            for cand in candidate_pdf_names:
                resolved = resolve_pdf_path(cand)
                if os.path.exists(resolved):
                    self.pdf_path = resolved
                    found_pdf = True
                    break

            if not found_pdf and candidate_pdf_names:
                self.pdf_path = resolve_pdf_path(candidate_pdf_names[0])

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
                self.preset_attempts = [
                    create_preset_attempt_record(
                        decision_dict=decision_dict,
                        violations_count=len(viol_list),
                        step=1,
                        default_action="ACCEPT_OUTPUT",
                    )
                ]

            self.current_result = {
                "decision": decision_dict,
                "violations": viol_list,
                "plan": plan_dict,
                "dom": dom_dict,
                "raw_dom": artifacts.get("raw_dom") or dom_dict,
                "diff": artifacts.get("diff") or {},
            }
            # Invalidate cached viewer_data so it rehydrates from the newly loaded run
            self.viewer_data = None

            conf_val = decision_dict.get("overall_confidence", 1.0)
            status_val = decision_dict.get("status", "ACCEPT")
            chosen_preset = decision_dict.get("chosen_preset", "docling_fast")

            # Cache loaded preset result for instant reuse without redundant reruns
            if dom_dict:
                self._preset_cache.put(
                    pdf_path=self.pdf_path,
                    preset=chosen_preset,
                    result=self.current_result,
                    language=self.language,
                    candidate_paths=candidate_pdf_names,
                )

            self._progress_tracker.set_loaded_run(
                output_dir=self.output_dir,
                document_display=self.pdf_path or dom_dict.get("source_filename", "N/A"),
                preset=chosen_preset,
                confidence=conf_val,
                status=status_val,
                nodes_count=len(dom_dict.get("nodes", [])),
                violations_count=len(viol_list),
            )

            return {
                "output_dir": self.output_dir,
                "document_path": self.pdf_path,
                "decision": decision_dict,
                "plan": plan_dict,
                "violations_count": len(viol_list),
                "attempts": list(self.preset_attempts),
            }

    # -------------------------------------------------------------------------
    # Progress Tracker Delegation
    # -------------------------------------------------------------------------

    def get_progress(self) -> Dict[str, Any]:
        """Thread-safe retrieval of current progress state."""
        return self._progress_tracker.get_progress()

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
        self._progress_tracker.update_progress(
            progress=progress,
            step_index=step_index,
            current_step=current_step,
            log=log,
            status=status,
            completed=completed,
            error=error,
        )

    def make_progress_callback(self) -> Callable[[int, str, str], None]:
        """Creates a standardized progress callback function wired to this session."""
        return self._progress_tracker.make_progress_callback()

    def add_log(self, message: str) -> None:
        """Thread-safe appending of a log message."""
        self._progress_tracker.add_log(message)

    def reset_progress(self, initial_step: str = "Starting...", log: Optional[str] = None) -> None:
        """Thread-safe reset of progress state to initiate a new run."""
        self._progress_tracker.reset_progress(initial_step=initial_step, log=log)

    def set_error(self, error_msg: str, log: Optional[str] = None) -> None:
        """Thread-safe recording of an execution error."""
        self._progress_tracker.set_error(error_msg=error_msg, log=log)

    def set_completed(
        self,
        status: str,
        confidence: float,
        violations_count: int,
        log: Optional[str] = None,
    ) -> None:
        """Thread-safe recording of a successful pipeline run completion."""
        self._progress_tracker.set_completed(
            status=status,
            confidence=confidence,
            violations_count=violations_count,
            log=log,
        )

    # -------------------------------------------------------------------------
    # Results & Viewer Hydration
    # -------------------------------------------------------------------------

    def get_results(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Thread-safe retrieval of preset comparison results."""
        with self._lock:
            if output_dir and output_dir != self.output_dir:
                self.load_previous_run(output_dir)
            elif not self.preset_attempts and not self.current_result:
                self.load_previous_run(self.output_dir or "output")
            v_list = normalize_violations(self.current_result.get("violations")) if self.current_result else []
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

            artifacts = load_run_artifacts(target_full)
            dom_data = artifacts["dom"] or {
                "document_id": "doc_init",
                "source_filename": self.pdf_path or "Document 8.pdf",
                "total_pages": 1,
                "nodes": [],
            }
            violations_data = artifacts["violations"]
            decision_data = artifacts["decision"] or {
                "chosen_preset": "docling_fast",
                "overall_confidence": 1.0,
                "status": "ACCEPT",
                "attempts": list(self.preset_attempts),
            }
            plan_data = artifacts["plan"]

            candidates = [
                self.pdf_path,
                dom_data.get("source_filename"),
                (plan_data.get("document_path") if plan_data else None),
                "src/e2e/Document 8.pdf",
            ]
            pdf_path = ""
            for cand in candidates:
                if cand:
                    res = resolve_pdf_path(str(cand))
                    if os.path.exists(res):
                        pdf_path = res
                        break
            if not pdf_path:
                pdf_path = resolve_pdf_path(str(candidates[0] or "src/e2e/Document 8.pdf"))
            total_pages = dom_data.get("total_pages", 1) or 1

            page_images, page_dimensions = load_or_render_page_images(
                pdf_path=pdf_path,
                target_dir=target_full,
                total_pages=total_pages,
            )

            if not decision_data.get("attempts") and self.preset_attempts:
                decision_data["attempts"] = list(self.preset_attempts)

            self.viewer_data = build_viewer_dataset(
                dom=dom_data,
                violations=violations_data,
                decision=decision_data,
                plan=plan_data,
                pdf_path=pdf_path,
                language=self.language or decision_data.get("language", "en"),
                page_images=page_images,
                page_dimensions=page_dimensions,
                total_pages=total_pages,
                output_dir=target_dir,
                raw_dom=artifacts.get("raw_dom"),
                diff=artifacts.get("diff"),
            )
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
            violations_list = normalize_violations(result.get("violations", []))
            total_pages = dom_dict.get("total_pages", 1) or 1

            page_images, page_dimensions = load_or_render_page_images(
                pdf_path=resolved_path,
                target_dir=self.output_dir or "output",
                total_pages=total_pages,
            )

            self.viewer_data = build_viewer_dataset(
                dom=dom_dict,
                violations=violations_list,
                decision=decision_dict,
                plan=result.get("plan"),
                pdf_path=resolved_path,
                language=language,
                page_images=page_images,
                page_dimensions=page_dimensions,
                total_pages=total_pages,
                output_dir=self.output_dir or "output",
                raw_dom=result.get("raw_dom") or dom_dict,
                diff=result.get("diff") or {},
            )

            preset_name = decision_dict.get("chosen_preset") or "docling_fast"

            # Sync preset attempts
            attempts = decision_dict.get("attempts", [])
            if attempts:
                self.preset_attempts = list(attempts)
            else:
                record = create_preset_attempt_record(
                    decision_dict=decision_dict,
                    violations_count=len(violations_list),
                    step=len(self.preset_attempts) + 1,
                    default_action="ACCEPT_PARSE",
                )
                existing_idx = next(
                    (i for i, a in enumerate(self.preset_attempts) if a.get("preset") == preset_name),
                    -1,
                )
                if existing_idx != -1:
                    self.preset_attempts[existing_idx] = record
                else:
                    self.preset_attempts.append(record)

            # Cache executed preset result for reuse
            self._preset_cache.put(
                pdf_path=resolved_path,
                preset=preset_name,
                result=self.current_result,
                language=language,
            )

    def _make_cache_keys(self, pdf_path: str, preset: str, language: Optional[str] = None) -> List[str]:
        """Constructs canonical lookup keys delegating to PresetCache."""
        return self._preset_cache.make_cache_keys(pdf_path, preset, language)

    def get_cached_preset_result(
        self,
        pdf_path: str,
        preset: str,
        language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves previously computed or loaded pipeline result for a document and preset if available.
        Checks in-memory preset cache, current session result, and completed previous runs on disk.
        """
        with self._lock:
            # 1. In-memory cache check
            cached = self._preset_cache.get(pdf_path, preset, language)
            if cached is not None:
                return cached

            doc_base = os.path.basename(pdf_path).strip().lower() if pdf_path else ""
            preset_clean = preset.strip().lower() if preset else "docling_fast"

            # 2. Check if current_result matches requested preset and document
            if self.current_result:
                curr_dec = self.current_result.get("decision", {})
                curr_preset = (curr_dec.get("chosen_preset") or "").strip().lower()
                curr_doc = os.path.basename(self.pdf_path).strip().lower() if self.pdf_path else ""
                if curr_preset == preset_clean and (not doc_base or not curr_doc or curr_doc == doc_base):
                    return dict(self.current_result)

            # 3. Search completed previous runs in repository on disk
            return self._preset_cache.find_in_previous_runs(
                pdf_path=pdf_path,
                preset=preset,
                previous_runs=self.get_previous_runs(),
                repo_root=self.repo_root,
                language=language,
            )

    def get_runs_grid(self, document_name: Optional[str] = None) -> Dict[str, Any]:
        """Thread-safe retrieval of previous runs table grid for a given document."""
        with self._lock:
            runs = self.get_previous_runs()
            target = document_name
            if not target and self.pdf_path:
                target = os.path.basename(self.pdf_path)
            return build_runs_grid(runs, target_file=target)
