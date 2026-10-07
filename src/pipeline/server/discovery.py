"""
src/pipeline/server/discovery.py

Scanning and discovery of previous pipeline execution outputs,
and construction of page-by-run matrix comparison grids.
"""

from __future__ import annotations

import glob
import logging
import os
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, List, Optional, Set

from src.pipeline.server.artifacts import load_run_artifacts
from src.pipeline.server.http_utils import REPO_ROOT

logger = logging.getLogger("cernodata.server.discovery")


@dataclass
class RunMetadata:
    """Strongly-typed metadata container for discovered pipeline execution outputs."""
    id: str
    dir_path: str
    document_name: str
    document_path: str
    chosen_preset: str
    status: str
    overall_confidence: float
    violations_count: int
    timestamp: str
    has_viewer: bool
    has_dom: bool
    has_plan: bool
    total_pages: int
    per_page_confidence: Dict[str, float] = field(default_factory=dict)
    per_page_violations: Dict[str, int] = field(default_factory=dict)
    per_page_nodes: Dict[str, int] = field(default_factory=dict)
    label: str = ""

    @classmethod
    def from_run_artifacts(
        cls,
        norm_rel: str,
        match: str,
        artifacts: Dict[str, Any],
    ) -> RunMetadata:
        """Constructs canonical RunMetadata directly from load_run_artifacts output."""
        plan_data = artifacts.get("plan")
        dom_data = artifacts.get("dom") or {}
        violations = artifacts.get("violations") or []
        decision_data = artifacts.get("decision") or {}

        active_violations = [
            v for v in violations
            if str(v.get("suppressed", "false")).lower() not in ("true", "1")
            and not v.get("accepted")
            and not v.get("is_fixed")
        ]
        violations_count = len(active_violations)

        overall_confidence = artifacts.get("overall_confidence")
        status = artifacts.get("status", "ACCEPT")

        diff_data = artifacts.get("diff") or {}
        diff_scoring = diff_data.get("scoring") or {}
        if diff_scoring:
            if diff_scoring.get("current_overall_confidence") is not None:
                overall_confidence = float(diff_scoring["current_overall_confidence"])
            if diff_scoring.get("status"):
                status = str(diff_scoring["status"])

        conf_val = float(overall_confidence) if overall_confidence is not None else 1.0
        doc_name = str(artifacts.get("document_name") or "Unknown")
        chosen_preset = str(artifacts.get("chosen_preset") or "docling_fast")
        score_str = f"{conf_val:.4f}"
        label = f"{doc_name} [{chosen_preset} | {status} {score_str} | {violations_count} viols] ({norm_rel})"

        per_page_viols: Dict[str, int] = {}
        for v in active_violations:
            p_num = str(v.get("global_page_index") or v.get("page") or 1)
            per_page_viols[p_num] = per_page_viols.get(p_num, 0) + 1

        per_page_nodes: Dict[str, int] = {}
        for n in dom_data.get("nodes", []):
            p_num = str(n.get("global_page_index") or n.get("temp_slice_index") or 1)
            per_page_nodes[p_num] = per_page_nodes.get(p_num, 0) + 1

        return cls(
            id=norm_rel,
            dir_path=norm_rel,
            document_name=doc_name,
            document_path=str(artifacts.get("document_path") or ""),
            chosen_preset=chosen_preset,
            status=status,
            overall_confidence=conf_val,
            violations_count=violations_count,
            timestamp=str(plan_data.get("created_at") or "") if plan_data else "",
            has_viewer=os.path.exists(os.path.join(match, "interactive_viewer.html")),
            has_dom=bool(dom_data),
            has_plan=plan_data is not None,
            total_pages=int(dom_data.get("total_pages", 1) or 1),
            per_page_confidence=decision_data.get("per_page_confidence") or {},
            per_page_violations=per_page_viols,
            per_page_nodes=per_page_nodes,
            label=label,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes metadata record to dictionary for API backwards compatibility."""
        return asdict(self)

    def evolve(self, **changes: Any) -> RunMetadata:
        """Derives a new record copying unchanged fields and updating only specified deltas."""
        return replace(self, **changes)


def find_previous_runs(repo_root: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Discovers completed output directories containing pipeline execution results,
    plans, DOM structures, or quality violation logs across standard output paths.

    Args:
        repo_root: Root repository directory. Defaults to detected repository root.

    Returns:
        List of summarized previous run metadata dictionaries.
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
            base_run = RunMetadata.from_run_artifacts(norm_rel, match, artifacts)

            decision_data = artifacts.get("decision") or {}

            attempts = decision_data.get("attempts", [])
            if attempts and len(attempts) > 1:
                for att in attempts:
                    att_preset = att.get("preset", base_run.chosen_preset)
                    att_step = att.get("step", 1)
                    att_id = f"{norm_rel}:step_{att_step}"
                    is_active = (att_preset == base_run.chosen_preset)

                    att_conf = att.get("overall_confidence")
                    if att_conf is None:
                        att_conf = base_run.overall_confidence if is_active else 1.0

                    att_status = att.get("status") or (base_run.status if is_active else "ACCEPT")

                    att_viols = att.get("violations_count")
                    if att_viols is None:
                        att_viols = base_run.violations_count if is_active else 0

                    att_page_conf = att.get("per_page_confidence")
                    if not att_page_conf:
                        att_page_conf = base_run.per_page_confidence if is_active else {}

                    att_page_viols = att.get("per_page_violations")
                    if not att_page_viols:
                        att_page_viols = base_run.per_page_violations if is_active else {}

                    conf_str = f"{float(att_conf):.4f}" if att_conf is not None else "1.0000"
                    att_label = (
                        f"{base_run.document_name} [{att_preset} (Step {att_step}) | "
                        f"{att_status} {conf_str} | {att_viols} viols] ({norm_rel})"
                    )

                    step_run = base_run.evolve(
                        id=att_id,
                        chosen_preset=att_preset,
                        status=att_status,
                        overall_confidence=float(att_conf) if att_conf is not None else 1.0,
                        violations_count=int(att_viols),
                        per_page_confidence=att_page_conf,
                        per_page_violations=att_page_viols,
                        label=att_label,
                    )
                    runs.append(step_run.to_dict())
            else:
                runs.append(base_run.to_dict())

    runs.sort(key=lambda r: (r["dir_path"] != "output", r["dir_path"]))
    return runs


def build_runs_grid(runs: List[Dict[str, Any]], target_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Builds a table grid structure of previous runs for a given file.

    Horizontal axis: page numbers (1..max_pages).
    Vertical axis: parsing run identifiers (run_id / preset).

    Args:
        runs: Discovered previous runs list.
        target_file: Document name filter. If None, defaults to first available document.

    Returns:
        Structured matrix grid payload for front-end presentation.
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
            page_conf = r.get("per_page_confidence", {})
            conf = page_conf.get(p_str)
            if conf is None:
                conf = page_conf.get(p)

            viols = r.get("per_page_violations", {}).get(p_str, 0)
            nodes = r.get("per_page_nodes", {}).get(p_str, 0)

            if conf is not None:
                is_passed = conf >= 0.85
            else:
                is_passed = (r.get("status") == "ACCEPT")

            pages_data[p_str] = {
                "page": p,
                "confidence": conf,
                "violations_count": viols,
                "nodes_count": nodes,
                "is_passed": is_passed,
            }

        run_id = str(r.get("id") or r.get("dir_path") or "output")
        dir_path = str(r.get("dir_path") or "output")
        preset = str(r.get("chosen_preset") or "docling_fast")
        status_val = str(r.get("status") or "ACCEPT")
        raw_conf = r.get("overall_confidence")
        overall_conf = float(raw_conf) if raw_conf is not None else 1.0
        violations_cnt = int(r.get("violations_count") or 0)
        timestamp_val = str(r.get("timestamp") or "")

        matrix_rows.append({
            "run_id": run_id,
            "dir_path": dir_path,
            "preset": preset,
            "status": status_val,
            "overall_confidence": overall_conf,
            "violations_count": violations_cnt,
            "timestamp": timestamp_val,
            "pages_data": pages_data,
        })

    return {
        "selected_file": selected_file,
        "available_files": available_files,
        "pages": pages,
        "runs": matrix_rows,
    }
