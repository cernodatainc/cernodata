"""
src/pipeline/server/run_mapping_synthesis.py

Pure synthesis steps that combine discovered documents, discovered runs, and
persisted mappings into the hierarchical file-set -> document -> runs structure.
"""

from __future__ import annotations

import glob
import os
from typing import Any, Dict, List, Optional, Set

from src.parsers.pdf_utils import get_pdf_page_count
from src.pipeline.server.run_mapping_helpers import (
    is_excluded_path,
    is_test_or_cache_dir,
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
    base = os.path.basename(candidate).lower()
    if not any(os.path.basename(p).lower() == base for p in doc_paths):
        doc_paths.add(candidate)


def discover_document_paths(
    root: str,
    available_docs: Optional[List[str]],
    persistent_data: Dict[str, Any],
    discovered_runs: List[Dict[str, Any]],
    forgotten_files: Optional[Set[str]] = None,
) -> Set[str]:
    """Collects candidate document paths from disk, persisted mappings, and discovered runs."""
    ignored = forgotten_files or set()

    def _is_forgotten(path_str: str) -> bool:
        if not path_str or not ignored:
            return False
        norm = normalize_path(path_str)
        base = os.path.basename(norm)
        return norm in ignored or base in ignored

    doc_paths: Set[str] = set()
    if available_docs:
        for d in available_docs:
            if not _is_forgotten(d) and not is_excluded_path(d, repo_root=root):
                _add_unique_doc_path(doc_paths, normalize_path(d))

    for pat in (
        os.path.join(root, "src", "e2e", "*.pdf"),
        os.path.join(root, "output", "*.pdf"),
        os.path.join(root, "*.pdf"),
    ):
        for match in glob.glob(pat):
            try:
                rel = normalize_path(os.path.relpath(match, root))
            except ValueError:
                rel = normalize_path(match)
            if not _is_forgotten(rel) and not is_excluded_path(rel, repo_root=root):
                _add_unique_doc_path(doc_paths, rel)

    for p_key, p_val in persistent_data.items():
        if p_key.startswith("_") or not isinstance(p_val, dict) or _is_forgotten(p_key):
            continue
        if not is_excluded_path(p_key, repo_root=root):
            _add_unique_doc_path(doc_paths, normalize_path(p_key))

    for r in discovered_runs:
        d_path = r.get("document_path")
        if d_path and not d_path.startswith("_") and not _is_forgotten(d_path) and not is_excluded_path(d_path, repo_root=root):
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
    base_t = os.path.basename(norm_t).lower()
    for k, v in doc_mappings.items():
        if str(v.get("file_name", "")).lower() == base_t:
            return k
    return None


def associate_discovered_runs(
    doc_mappings: Dict[str, Dict[str, Any]],
    discovered_runs: List[Dict[str, Any]],
    forgotten_files: Optional[Set[str]] = None,
) -> None:
    """Attaches discovered runs to their documents, creating entries for unknown documents."""
    ignored = forgotten_files or set()

    def _is_forgotten(path_str: str) -> bool:
        if not path_str or not ignored:
            return False
        norm = normalize_path(path_str)
        base = os.path.basename(norm)
        return norm in ignored or base in ignored

    for r in discovered_runs:
        r_doc_path = normalize_path(r.get("document_path") or "")
        r_doc_name = r.get("document_name") or os.path.basename(r_doc_path)
        if _is_forgotten(r_doc_path) or _is_forgotten(r_doc_name):
            continue
        if is_test_or_cache_dir(r_doc_path) or is_test_or_cache_dir(r_doc_name):
            continue

        run_id = r.get("id") or r.get("dir_path") or "output"
        output_dir = r.get("dir_path") or "output"
        if is_test_or_cache_dir(run_id) or is_test_or_cache_dir(output_dir):
            continue
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


def _is_persisted_run_page_count_valid(
    p_run: Dict[str, Any],
    doc_path: str,
    repo_root: Optional[str],
) -> bool:
    """Validates a persisted run's total_pages against positive bounds and actual PDF page count."""
    raw_pages = p_run.get("total_pages")
    if raw_pages is None:
        return True
    try:
        run_pages = int(raw_pages)
    except (ValueError, TypeError):
        return False
    if run_pages < 1:
        return False
    if repo_root and doc_path:
        norm = doc_path.replace("\\", "/")
        base = os.path.basename(norm)
        for cand in (
            norm if os.path.isabs(norm) else os.path.join(repo_root, norm),
            os.path.join(repo_root, "src", "e2e", base),
            os.path.join(repo_root, "output", base),
            os.path.join(repo_root, base),
        ):
            if os.path.isfile(cand):
                actual_pages = get_pdf_page_count(cand)
                if actual_pages is not None and actual_pages >= 1 and run_pages != actual_pages:
                    return False
                break
    return True


def merge_persistent_runs(
    doc_mappings: Dict[str, Dict[str, Any]],
    persistent_data: Dict[str, Any],
    removed_runs: Set[str],
    repo_root: Optional[str] = None,
) -> None:
    """Integrates persisted run records (e.g. if a run folder was moved or archived)."""
    for p_path, p_val in persistent_data.items():
        if p_path.startswith("_") or not isinstance(p_val, dict):
            continue
        norm_p = normalize_path(p_path)
        matched_key = _match_doc_key(doc_mappings, norm_p)
        if not matched_key:
            continue
        target_runs = doc_mappings[matched_key]["runs"]
        base_p = os.path.basename(norm_p)
        for p_run in p_val.get("runs", []):
            r_id = normalize_path(str(p_run.get("run_id") or ""))
            r_out = normalize_path(str(p_run.get("output_dir") or ""))
            if _is_persistent_run_removed(r_id, r_out, norm_p, base_p, removed_runs):
                continue
            if not _is_persisted_run_page_count_valid(p_run, norm_p, repo_root):
                continue
            if not any(x["run_id"] == p_run.get("run_id") for x in target_runs):
                target_runs.append(p_run)


def _is_persistent_run_removed(
    r_id: str,
    r_out: str,
    norm_doc: str,
    doc_base: str,
    removed_runs: Set[str],
) -> bool:
    """Checks whether a persisted run record matches any scoped or unscoped removal key."""
    if r_id and r_id != "output" and r_id in removed_runs:
        return True
    if not r_id and r_out and r_out != "output" and r_out in removed_runs:
        return True
    for key in (r_id, r_out):
        if not key:
            continue
        if f"{norm_doc}::{key}" in removed_runs or (doc_base and f"{doc_base}::{key}" in removed_runs):
            return True
    return False


def group_into_file_sets(
    doc_mappings: Dict[str, Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Finalizes per-document summaries; returns (file_sets_list, all_mappings_list)."""
    file_sets_map: Dict[str, Dict[str, Any]] = {}
    all_mappings_list: List[Dict[str, Any]] = []

    for entry in doc_mappings.values():
        if is_excluded_path(str(entry.get("file_path", ""))):
            continue
        if str(entry.get("file_set", "")) == "test_output":
            continue
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
