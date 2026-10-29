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
from typing import Any, Dict, Iterable, List, Optional, Set, Union

from src.pipeline.server.artifacts import RunArtifacts
from src.pipeline.server.http_utils import REPO_ROOT
from src.schemas import ValidatedRunArtifacts, load_validated_run_artifacts

logger = logging.getLogger("cernodata.server.discovery")

PAGE_PASS_CONFIDENCE = 0.85
DEFAULT_OVERALL_CONFIDENCE = 1.0


def _max_int_key(keys: Iterable[Any], current: int) -> int:
    """Returns the max of `current` and all keys parseable as integers; non-numeric keys are skipped."""
    result = current
    for key in keys:
        try:
            result = max(result, int(key))
        except (ValueError, TypeError):
            logger.debug("Skipping non-numeric page key: %r", key)
    return result


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
        artifacts: Union[ValidatedRunArtifacts, RunArtifacts],
    ) -> RunMetadata:
        """Constructs canonical RunMetadata directly from validated artifacts."""
        if isinstance(artifacts, ValidatedRunArtifacts):
            active_viols_pages = [str(v.global_page_index) for v in artifacts.active_violations]
            node_pages = [str(n.global_page_index) for n in artifacts.dom.nodes]
            raw_conf: Optional[float] = artifacts.overall_confidence
            timestamp = artifacts.plan.created_at if artifacts.plan else ""
            has_dom = True
            has_plan = artifacts.plan is not None
            total_pages = artifacts.dom.total_pages
            per_page_conf = artifacts.decision.per_page_confidence
        else:
            active_viols = [
                item for item in artifacts.violations
                if str(item.get("suppressed", "false")).lower() not in ("true", "1")
                and not item.get("accepted")
                and not item.get("is_fixed")
            ]
            active_viols_pages = [str(v.get("global_page_index") or v.get("page") or 1) for v in active_viols]
            node_pages = [
                str(n.get("global_page_index") or n.get("temp_slice_index") or 1)
                for n in artifacts.dom.get("nodes", [])
            ]
            raw_conf = artifacts.overall_confidence
            timestamp = str(artifacts.plan.get("created_at") or "") if artifacts.plan else ""
            has_dom = bool(artifacts.dom)
            has_plan = artifacts.plan is not None
            total_pages = int(artifacts.dom.get("total_pages", 1) or 1)
            per_page_conf = artifacts.decision.get("per_page_confidence") or {}

        status = artifacts.status
        diff_scoring = (artifacts.diff or {}).get("scoring") or {}
        if diff_scoring:
            if diff_scoring.get("current_overall_confidence") is not None:
                raw_conf = float(diff_scoring["current_overall_confidence"])
            if diff_scoring.get("status"):
                status = str(diff_scoring["status"])

        conf_val = float(raw_conf) if raw_conf is not None else 1.0
        doc_name = artifacts.document_name or "Unknown"
        chosen_preset = artifacts.chosen_preset or "docling_fast"
        violations_count = len(active_viols_pages)
        label = f"{doc_name} [{chosen_preset} | {status} {conf_val:.4f} | {violations_count} viols] ({norm_rel})"

        per_page_viols: Dict[str, int] = {}
        for p_num in active_viols_pages:
            per_page_viols[p_num] = per_page_viols.get(p_num, 0) + 1

        per_page_nodes: Dict[str, int] = {}
        for p_num in node_pages:
            per_page_nodes[p_num] = per_page_nodes.get(p_num, 0) + 1

        return cls(
            id=norm_rel,
            dir_path=norm_rel,
            document_name=doc_name,
            document_path=artifacts.document_path or "",
            chosen_preset=chosen_preset,
            status=status,
            overall_confidence=conf_val,
            violations_count=violations_count,
            timestamp=timestamp,
            has_viewer=os.path.exists(os.path.join(match, "interactive_viewer.html")),
            has_dom=has_dom,
            has_plan=has_plan,
            total_pages=total_pages,
            per_page_confidence=per_page_conf,
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

            validated_artifacts = load_validated_run_artifacts(match)
            if validated_artifacts is None:
                # Corrupted or incomplete run failing schema contracts is dropped
                continue

            base_run = RunMetadata.from_run_artifacts(norm_rel, match, validated_artifacts)

            attempts = validated_artifacts.decision.attempts
            if attempts and len(attempts) > 1:
                for att in attempts:
                    att_preset = att.preset or base_run.chosen_preset
                    att_step = att.step
                    att_id = f"{norm_rel}:step_{att_step}"
                    is_active = (att_preset == base_run.chosen_preset)

                    att_conf = att.overall_confidence
                    if att_conf is None:
                        att_conf = base_run.overall_confidence if is_active else 1.0

                    att_status = att.status or (base_run.status if is_active else "ACCEPT")

                    att_viols = att.violations_count
                    if att_viols is None:
                        att_viols = base_run.violations_count if is_active else 0

                    att_page_conf = att.per_page_confidence or (base_run.per_page_confidence if is_active else {})
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
        for key_map in (r.get("per_page_confidence", {}), r.get("per_page_violations", {})):
            max_pages = _max_int_key(key_map.keys(), max_pages)

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
                is_passed = conf >= PAGE_PASS_CONFIDENCE
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
        overall_conf = float(raw_conf) if raw_conf is not None else DEFAULT_OVERALL_CONFIDENCE
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
