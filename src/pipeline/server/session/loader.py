"""
src/pipeline/server/session/loader.py

Artifact loading and session state rehydration from previous execution runs.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.pipeline.execution_models import AttemptRecord
from src.pipeline.planner.models import DocumentPlan
from src.pipeline.server.artifacts import (
    ViewerDataset,
    create_preset_attempt_record,
    load_run_artifacts,
)
from src.pipeline.server.http_utils import parse_run_dir_and_step
from src.utils import resolve_pdf_path

if TYPE_CHECKING:
    from src.pipeline.server.preset_cache import PresetCache
    from src.pipeline.server.progress import ProgressTracker

logger = logging.getLogger("cernodata.server.session.loader")


class RunLoaderMixin:
    """Mixin providing run artifact loading and session synchronization."""

    _lock: threading.RLock
    output_dir: str
    active_step: Optional[int]
    viewer_data: Optional[ViewerDataset]
    repo_root: str
    submitted_plan: Optional[DocumentPlan]
    language: str
    pdf_path: str
    preset_attempts: List[AttemptRecord]
    current_result: Optional[Dict[str, Any]]
    _preset_cache: PresetCache
    _progress_tracker: ProgressTracker

    def load_previous_run(self, output_dir: str) -> Dict[str, Any]:
        """
        Loads artifacts from an output directory into active session state.

        Args:
            output_dir: Directory path relative to repo root or absolute path.

        Returns:
            Summary of loaded artifacts and run attributes.
        """
        with self._lock:
            norm_rel, step_idx = parse_run_dir_and_step(output_dir)
            self.output_dir = norm_rel
            self.active_step = step_idx
            self.viewer_data = None
            full_dir = norm_rel if os.path.isabs(norm_rel) else os.path.join(self.repo_root, norm_rel)
            if not os.path.exists(full_dir):
                logger.warning("Requested output directory does not exist: %s", full_dir)
                return {}

            artifacts = load_run_artifacts(full_dir)
            plan_dict = artifacts.plan
            decision_dict = artifacts.decision
            dom_dict = artifacts.dom
            viol_list = artifacts.violations

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

            if not decision_dict:
                decision_dict = {}

            dec_language = decision_dict.get("language")
            if dec_language and not self.language:
                self.language = str(dec_language)

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

            raw_dom = artifacts.raw_dom or dom_dict
            diff = artifacts.diff or {}
            self.current_result = {
                "decision": decision_dict,
                "violations": viol_list,
                "plan": plan_dict,
                "dom": dom_dict,
                "raw_dom": raw_dom,
                "diff": diff,
            }
            # Invalidate cached viewer_data so it rehydrates from the newly loaded run
            self.viewer_data = None

            raw_conf = decision_dict.get("overall_confidence")
            conf_val = float(raw_conf) if raw_conf is not None else 0.0

            raw_status = decision_dict.get("status")
            status_val = str(raw_status) if raw_status is not None else "UNKNOWN"

            raw_chosen = decision_dict.get("chosen_preset")
            chosen_preset = str(raw_chosen) if raw_chosen is not None else "unknown"

            viol_count = len(viol_list)

            target_att = None
            if step_idx is not None and self.preset_attempts:
                for a in self.preset_attempts:
                    if a.get("step") == step_idx:
                        target_att = a
                        break
                if not target_att and 0 <= step_idx - 1 < len(self.preset_attempts):
                    target_att = self.preset_attempts[step_idx - 1]
            if target_att:
                chosen_preset = str(target_att.get("preset", chosen_preset))
                conf_val = float(target_att.get("overall_confidence", conf_val) or conf_val)
                status_val = str(target_att.get("status", status_val))
                viol_count = int(target_att.get("violations_count", viol_count))

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
                violations_count=viol_count,
            )

            return {
                "output_dir": self.output_dir,
                "document_path": self.pdf_path,
                "decision": decision_dict,
                "plan": plan_dict,
                "violations_count": viol_count,
                "attempts": list(self.preset_attempts),
                "active_step": self.active_step,
                "chosen_preset": chosen_preset,
                "overall_confidence": conf_val,
                "status": status_val,
            }
