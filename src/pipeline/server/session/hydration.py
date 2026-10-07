"""
src/pipeline/server/session/hydration.py

Results assembly and interactive visual viewer dataset hydration for server sessions.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

from src.pipeline.execution_models import AttemptRecord
from src.pipeline.server.artifacts import (
    ViewerDataset,
    build_viewer_dataset,
    create_preset_attempt_record,
    load_or_render_page_images,
    load_run_artifacts,
    normalize_violations,
)
from src.pipeline.server.http_utils import parse_run_dir_and_step
from src.utils import resolve_pdf_path

if TYPE_CHECKING:
    from src.pipeline.server.preset_cache import PresetCache


class ViewerHydrationMixin:
    """Mixin providing results formatting and visual viewer hydration datasets."""

    _lock: threading.RLock
    output_dir: str
    active_step: Optional[int]
    viewer_data: Optional[ViewerDataset]
    current_result: Optional[Dict[str, Any]]
    preset_attempts: List[AttemptRecord]
    repo_root: str
    pdf_path: str
    language: str
    _preset_cache: PresetCache

    def load_previous_run(self, output_dir: str) -> Dict[str, Any]:
        """Method stub implemented by RunLoaderMixin."""
        raise NotImplementedError

    def get_previous_runs(self) -> List[Dict[str, Any]]:
        """Method stub implemented by DocumentsMixin."""
        raise NotImplementedError

    def get_results(self, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Thread-safe retrieval of preset comparison results."""
        with self._lock:
            if output_dir and output_dir != self.output_dir:
                self.load_previous_run(output_dir)
            elif not self.preset_attempts and not self.current_result:
                target_to_load = self.output_dir or "output"
                target_full = target_to_load if os.path.isabs(target_to_load) else os.path.join(self.repo_root, target_to_load)
                if not os.path.exists(target_full):
                    try:
                        prev = self.get_previous_runs()
                        if prev and prev[0].get("dir_path"):
                            target_to_load = prev[0]["dir_path"]
                    except Exception:
                        pass
                self.load_previous_run(target_to_load)
            v_list = normalize_violations(self.current_result.get("violations")) if self.current_result else []
            return {
                "attempts": list(self.preset_attempts),
                "decision": self.current_result.get("decision") if self.current_result else None,
                "violations": v_list,
                "output_dir": self.output_dir or "output",
            }

    def get_viewer_data(self, output_dir: Optional[str] = None) -> ViewerDataset:
        """Thread-safe retrieval and hydration of viewer state."""
        with self._lock:
            if output_dir:
                norm_rel, step_idx = parse_run_dir_and_step(output_dir)
                if norm_rel != self.output_dir or step_idx != self.active_step:
                    self.load_previous_run(output_dir)

            if self.viewer_data is not None:
                return self.viewer_data

            target_dir = self.output_dir or "output"
            target_full = target_dir if os.path.isabs(target_dir) else os.path.join(self.repo_root, target_dir)

            artifacts = load_run_artifacts(target_full)
            dom_data = artifacts.dom or (self.current_result.get("dom") if self.current_result and not output_dir else None)
            if not dom_data:
                # If target directory is the unexecuted default 'output', attempt fallback to existing completed runs
                if (not output_dir or output_dir == "output") and (self.output_dir == "output" or not self.output_dir):
                    try:
                        previous_runs = self.get_previous_runs()
                        for prev_entry in previous_runs:
                            prev_dir = prev_entry.get("dir_path")
                            if prev_dir and prev_dir != "output":
                                prev_full = prev_dir if os.path.isabs(prev_dir) else os.path.join(self.repo_root, prev_dir)
                                prev_artifacts = load_run_artifacts(prev_full)
                                if prev_artifacts.dom:
                                    self.load_previous_run(prev_dir)
                                    return self.get_viewer_data(output_dir=prev_dir)
                    except Exception:
                        pass

                raise ValueError(
                    f"DocumentDOM artifact is missing or empty in run directory '{target_full}'. "
                    "Ensure pipeline has produced document_dom.json before hydrating viewer."
                )

            decision_data = artifacts.decision or (self.current_result.get("decision") if self.current_result and not output_dir else None)
            if not decision_data:
                raise ValueError(
                    f"Decision artifact is missing or empty in run directory '{target_full}'. "
                    "Ensure pipeline has produced decision_tree.json or plan_execution_result.json."
                )

            plan_data = artifacts.plan or (self.current_result.get("plan") if self.current_result else None)

            raw_violations = artifacts.violations
            if raw_violations is None and self.current_result:
                raw_violations = self.current_result.get("violations")
            violations_data = normalize_violations(raw_violations if raw_violations is not None else [])

            candidate_paths: List[Optional[str]] = [
                self.pdf_path,
                dom_data.get("source_filename"),
                plan_data.get("document_path") if plan_data else None,
                artifacts.document_path,
            ]
            resolved_pdf: Optional[str] = None
            for cand in candidate_paths:
                if cand:
                    cand_resolved = resolve_pdf_path(str(cand))
                    if os.path.exists(cand_resolved):
                        resolved_pdf = cand_resolved
                        break

            if not resolved_pdf:
                first_cand = next((str(c) for c in candidate_paths if c), None)
                if first_cand:
                    resolved_pdf = resolve_pdf_path(first_cand)
                else:
                    raise FileNotFoundError(
                        f"Cannot locate source PDF for run '{target_full}'. "
                        "No document_path specified in session, DOM, or execution plan."
                    )

            pdf_path = resolved_pdf

            raw_pages = dom_data.get("total_pages")
            if raw_pages is None:
                raise ValueError(f"DocumentDOM is missing required 'total_pages' in '{target_full}'.")
            total_pages = int(raw_pages)
            if total_pages < 1:
                raise ValueError(f"DocumentDOM has non-positive total_pages ({total_pages}) in '{target_full}'.")

            page_images, page_dimensions = load_or_render_page_images(
                pdf_path=pdf_path,
                target_dir=target_full,
                total_pages=total_pages,
            )

            if not decision_data.get("attempts") and self.preset_attempts:
                decision_data["attempts"] = list(self.preset_attempts)

            viewer_language = self.language or decision_data.get("language", "en")
            raw_dom = artifacts.raw_dom or dom_data
            diff = artifacts.diff or {}

            self.viewer_data = build_viewer_dataset(
                dom=dom_data,
                violations=violations_data,
                decision=decision_data,
                plan=plan_data,
                pdf_path=pdf_path,
                language=viewer_language,
                page_images=page_images,
                page_dimensions=page_dimensions,
                total_pages=total_pages,
                output_dir=target_dir,
                raw_dom=raw_dom,
                diff=diff,
            )
            if self.active_step is not None:
                self.viewer_data["activeStep"] = self.active_step
            return self.viewer_data

    def update_result_state(self, result: Mapping[str, Any], pdf_path: str, language: str) -> None:
        """Thread-safe update of server result state and hydration dataset."""
        resolved_path = resolve_pdf_path(pdf_path)
        with self._lock:
            self.current_result = dict(result)
            self.pdf_path = resolved_path
            self.language = language

            dom_dict = result.get("dom")
            if not dom_dict:
                raise ValueError("Pipeline execution result must contain a non-empty 'dom' mapping.")

            decision_dict = result.get("decision")
            if not decision_dict:
                raise ValueError("Pipeline execution result must contain a non-empty 'decision' mapping.")

            violations_list = normalize_violations(result.get("violations", []))
            raw_pages = dom_dict.get("total_pages")
            if raw_pages is None:
                raise ValueError("DocumentDOM in execution result is missing 'total_pages'.")
            total_pages = int(raw_pages)
            if total_pages < 1:
                raise ValueError(f"Invalid non-positive total_pages ({total_pages}) in DocumentDOM.")

            target_output_dir = self.output_dir or "output"
            page_images, page_dimensions = load_or_render_page_images(
                pdf_path=resolved_path,
                target_dir=target_output_dir,
                total_pages=total_pages,
            )

            plan = result.get("plan")
            raw_dom = result.get("raw_dom") or dom_dict
            diff = result.get("diff") or {}

            # If existing viewer_data has the same document and pages, update only changed fields
            existing = self.viewer_data
            if (
                existing is not None
                and existing.get("pdfSourceFile") == resolved_path
                and existing.get("totalPages") == total_pages
                and existing.get("outputDir") == target_output_dir
            ):
                updated_dataset: ViewerDataset = dict(existing)  # type: ignore[assignment]
                updated_dataset.update({
                    "dom": dom_dict,
                    "violations": violations_list,
                    "decision": decision_dict,
                    "plan": plan,
                    "activeLanguage": language,
                    "raw_dom": raw_dom,
                    "diff": diff,
                })
                self.viewer_data = updated_dataset
            else:
                self.viewer_data = build_viewer_dataset(
                    dom=dom_dict,
                    violations=violations_list,
                    decision=decision_dict,
                    plan=plan,
                    pdf_path=resolved_path,
                    language=language,
                    page_images=page_images,
                    page_dimensions=page_dimensions,
                    total_pages=total_pages,
                    output_dir=target_output_dir,
                    raw_dom=raw_dom,
                    diff=diff,
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
