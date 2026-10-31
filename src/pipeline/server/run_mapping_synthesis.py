"""
src/pipeline/server/run_mapping_synthesis.py

Pure synthesis steps that combine discovered documents, discovered runs, and
persisted mappings into the hierarchical file-set -> document -> runs structure.
"""

from __future__ import annotations

import glob
import os
from typing import Any, Dict, List, Optional, Set

from src.pipeline.server.run_mapping_helpers import (
    make_doc_entry,
    make_run_record,
    normalize_path,
)


def is_run_removed(r: Dict[str, Any], removed_runs: Set[str]) -> bool:
    """Returns True if a discovered run matches any recorded removal key."""
    r_id = normalize_path(str(r.get("id") or ""))
    r_dir = normalize_path(str(r.get("dir_path") or "output"))
    r_doc = normalize_path(str(r.get("document_path") or ""))
    r_doc_name = os.path.basename(r_doc) if r_doc else str(r.get("document_name") or "")
    if r_id != "output" and r_id in removed_runs:
        return True
    if r_dir != "output" and r_dir in removed_runs:
        return True
    if r_doc and (f"{r_doc}::{r_id}" in removed_runs or f"{r_doc}::{r_dir}" in removed_runs):
        return True
    if r_doc_name and (f"{r_doc_name}::{r_id}" in removed_runs or f"{r_doc_name}::{r_dir}" in removed_runs):
        return True
    return False


def _add_unique_doc_path(doc_paths: Set[str], candidate: str) -> None:
    """Adds a document path unless a document with the same base filename is known."""
    base = os.path.basename(candidate)
    if not any(os.path.basename(p) == base for p in doc_paths):
        doc_paths.add(candidate)


def discover_document_paths(
    root: str,
    available_docs: Optional[List[str]],
    persistent_data: Dict[str, Any],
    discovered_runs: List[Dict[str, Any]],
) -> Set[str]:
    """Collects candidate document paths from disk, persisted mappings, and discovered runs."""
    doc_paths: Set[str] = set()
    if available_docs:
        doc_paths.update(normalize_path(d) for d in available_docs)

    for pat in (
        os.path.join(root, "src", "e2e", "*.pdf"),
        os.path.join(root, "output", "*.pdf"),
        os.path.join(root, "*.pdf"),
    ):
        for match in glob.glob(pat):
            try:
                doc_paths.add(normalize_path(os.path.relpath(match, root)))
            except ValueError:
                doc_paths.add(normalize_path(match))

    for p_key, p_val in persistent_data.items():
        if p_key.startswith("_") or not isinstance(p_val, dict):
            continue
        _add_unique_doc_path(doc_paths, normalize_path(p_key))

    for r in discovered_runs:
        d_path = r.get("document_path")
        if d_path and not d_path.startswith("_"):
            _add_unique_doc_path(doc_paths, normalize_path(d_path))
    return doc_paths


def _build_discovered_run_entry(r: Dict[str, Any], run_id: str, output_dir: str) -> Dict[str, Any]:
    """Builds a mapping run entry from a discovered run payload."""
    entry = make_run_record(
        run_id=run_id,
        output_dir=output_dir,
        preset=r.get("chosen_preset") or "docling_fast",
        status=r.get("status") or "ACCEPT",
        confidence=float(r.get("overall_confidence", 1.0)),
        violations_count=int(r.get("violations_count", 0)),
        total_pages=int(r.get("total_pages", 1)),
        per_page_confidence=r.get("per_page_confidence", {}),
        per_page_violations=r.get("per_page_violations", {}),
        timestamp=r.get("timestamp") or "",
    )
    entry["has_viewer"] = r.get("has_viewer", False)
    entry["has_dom"] = r.get("has_dom", False)
    entry["has_plan"] = r.get("has_plan", False)
    entry["label"] = r.get("label", "")
    return entry


def _match_doc_key(doc_mappings: Dict[str, Dict[str, Any]], target: str) -> Optional[str]:
    """Finds the matching document key by full path or base filename."""
    if not target:
        return None
    norm_t = normalize_path(target)
    if norm_t in doc_mappings:
        return norm_t
    base_t = os.path.basename(norm_t)
    for k, v in doc_mappings.items():
        if v["file_name"] == base_t:
            return k
    return None


def associate_discovered_runs(
    doc_mappings: Dict[str, Dict[str, Any]],
    discovered_runs: List[Dict[str, Any]],
) -> None:
    """Attaches discovered runs to their documents, creating entries for unknown documents."""
    for r in discovered_runs:
        r_doc_path = normalize_path(r.get("document_path") or "")
        r_doc_name = r.get("document_name") or os.path.basename(r_doc_path)
        run_id = r.get("id") or r.get("dir_path") or "output"
        output_dir = r.get("dir_path") or "output"
        run_entry = _build_discovered_run_entry(r, run_id, output_dir)

        matched_key = _match_doc_key(doc_mappings, r_doc_path) or _match_doc_key(doc_mappings, r_doc_name)

        if not matched_key:
            # Document wasn't pre-discovered on disk, create entry for it
            candidate_key = r_doc_path or r_doc_name
            if candidate_key and not candidate_key.startswith("_"):
                matched_key = candidate_key
                doc_mappings[matched_key] = make_doc_entry(
                    matched_key, file_name=r_doc_name, with_summary=True
                )

        if matched_key:
            doc_entry = doc_mappings[matched_key]
            if not any(x["run_id"] == run_id for x in doc_entry["runs"]):
                doc_entry["runs"].append(run_entry)


def merge_persistent_runs(
    doc_mappings: Dict[str, Dict[str, Any]],
    persistent_data: Dict[str, Any],
    removed_runs: Set[str],
) -> None:
    """Integrates persisted run records (e.g. if a run folder was moved or archived)."""
    for p_path, p_val in persistent_data.items():
        if p_path.startswith("_") or not isinstance(p_val, dict):
            continue
        norm_p = normalize_path(p_path)
        if norm_p not in doc_mappings:
            continue
        target_runs = doc_mappings[norm_p]["runs"]
        for p_run in p_val.get("runs", []):
            r_id = p_run.get("run_id")
            r_out = p_run.get("output_dir")
            if r_id in removed_runs or r_out in removed_runs:
                continue
            if not any(x["run_id"] == r_id for x in target_runs):
                target_runs.append(p_run)


def group_into_file_sets(
    doc_mappings: Dict[str, Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Finalizes per-document summaries; returns (file_sets_list, all_mappings_list)."""
    file_sets_map: Dict[str, Dict[str, Any]] = {}
    all_mappings_list: List[Dict[str, Any]] = []

    for entry in doc_mappings.values():
        runs_list = entry["runs"]
        # Sort runs: output first, then by run_id
        runs_list.sort(key=lambda x: (x["output_dir"] != "output", x["run_id"]))
        entry["runs_count"] = len(runs_list)
        entry["latest_run"] = runs_list[0] if runs_list else None
        all_mappings_list.append(entry)

        f_set = entry["file_set"]
        bucket = file_sets_map.setdefault(
            f_set,
            {"file_set": f_set, "document_count": 0, "runs_count": 0, "documents": []},
        )
        bucket["documents"].append(entry)
        bucket["document_count"] += 1
        bucket["runs_count"] += len(runs_list)

    file_sets_list = sorted(file_sets_map.values(), key=lambda s: str(s["file_set"]))
    return file_sets_list, all_mappings_list


def pick_active_selection(all_mappings_list: List[Dict[str, Any]]) -> tuple[str, str]:
    """Selects the first document that has runs (and its latest run) as the active view."""
    for entry in all_mappings_list:
        if entry.get("runs"):
            latest = entry.get("latest_run") or entry["runs"][0]
            return (
                str(entry["file_path"]),
                str(latest.get("output_dir") or latest.get("run_id") or ""),
            )
    if all_mappings_list:
        return str(all_mappings_list[0]["file_path"]), ""
    return "", ""
