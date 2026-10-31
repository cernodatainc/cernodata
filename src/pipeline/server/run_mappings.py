"""
src/pipeline/server/run_mappings.py

Persistent mapping repository and discovery service linking input document files
and file sets to historical pipeline parsing runs.

Pure path/record helpers live in run_mapping_helpers.py and the discovery
synthesis steps live in run_mapping_synthesis.py.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import shutil
import threading
from typing import Any, Dict, List, Optional, Set

from src.pipeline.server.discovery import find_previous_runs
from src.pipeline.server.http_utils import REPO_ROOT
from src.pipeline.server.run_mapping_helpers import (
    derive_file_set,
    make_doc_entry as _make_doc_entry,
    make_run_record as _make_run_record,
    normalize_path,
)
from src.pipeline.server.run_mapping_synthesis import (
    associate_discovered_runs,
    discover_document_paths,
    group_into_file_sets,
    is_run_removed as _is_run_removed,
    merge_persistent_runs,
    pick_active_selection,
)
from src.utils import safe_load_json

logger = logging.getLogger("cernodata.server.run_mappings")

__all__ = [
    "MAPPINGS_FILENAME",
    "derive_file_set",
    "get_file_run_mappings",
    "get_mappings_file_path",
    "load_persistent_mappings",
    "normalize_path",
    "record_run_mapping",
    "remove_run_mapping",
    "save_persistent_mappings",
]

_LOCK = threading.RLock()
MAPPINGS_FILENAME = "run_mappings.json"

_ROOT_OUTPUT_ARTIFACTS = (
    "plan_execution_result.json",
    "document_dom.json",
    "plan.json",
    "interactive_viewer.html",
    "quality_violations.json",
)


def _safe_remove(path: str) -> None:
    """Removes a file if it exists, logging (not raising) on OS errors."""
    if not os.path.isfile(path):
        return
    try:
        os.remove(path)
    except OSError as ex:
        logger.debug("Failed to remove %s: %s", path, ex)


def get_mappings_file_path(repo_root: Optional[str] = None) -> str:
    """Returns absolute path to the persistent run_mappings.json store."""
    root = repo_root or REPO_ROOT
    out_dir = os.path.join(root, "output")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, MAPPINGS_FILENAME)


def load_persistent_mappings(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """Loads recorded file-to-run mappings from disk if present."""
    data = safe_load_json(get_mappings_file_path(repo_root), {})
    return data if isinstance(data, dict) else {}


def save_persistent_mappings(mappings: Dict[str, Any], repo_root: Optional[str] = None) -> None:
    """Persists file-to-run mappings dictionary to disk."""
    path = get_mappings_file_path(repo_root)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(mappings, f, indent=2)
    except Exception as ex:
        logger.warning("Failed to save run mappings to %s: %s", path, ex)


def _read_removed_keys(mappings: Dict[str, Any]) -> List[str]:
    """Returns the recorded removal keys list, tolerating malformed payloads."""
    raw = mappings.get("_removed_runs", [])
    return raw if isinstance(raw, list) else []


def record_run_mapping(
    document_path: str,
    run_id: str,
    output_dir: str,
    preset: str,
    status: str,
    confidence: float,
    violations_count: int,
    total_pages: int = 1,
    per_page_confidence: Optional[Dict[str, float]] = None,
    per_page_violations: Optional[Dict[str, int]] = None,
    timestamp: str = "",
    repo_root: Optional[str] = None,
) -> None:
    """
    Records an execution run mapping for an input document and persists it to disk.
    """
    with _LOCK:
        mappings = load_persistent_mappings(repo_root)
        norm_path = normalize_path(document_path)
        doc_entry = mappings.setdefault(norm_path, _make_doc_entry(norm_path))

        run_record = _make_run_record(
            run_id, output_dir, preset, status, confidence, violations_count,
            total_pages, per_page_confidence, per_page_violations, timestamp,
        )

        # Avoid duplicates for same run_id
        existing_runs = doc_entry.get("runs", [])
        idx = next((i for i, r in enumerate(existing_runs) if r.get("run_id") == run_id), None)
        if idx is not None:
            existing_runs[idx] = run_record
        else:
            existing_runs.append(run_record)

        doc_entry["runs"] = existing_runs
        save_persistent_mappings(mappings, repo_root)


def _record_removal_keys(
    mappings: Dict[str, Any],
    norm_run: Optional[str],
    norm_out: Optional[str],
    norm_doc: Optional[str],
    doc_base: Optional[str],
) -> None:
    """Adds removal keys to mappings without suppressing the shared "output" folder."""
    removed_set = set(_read_removed_keys(mappings))
    for item in (norm_run, norm_out):
        if item and item != "output":
            removed_set.add(item)
        elif item == "output" and norm_doc:
            removed_set.add(f"{norm_doc}::{item}")
            if doc_base:
                removed_set.add(f"{doc_base}::{item}")
    mappings["_removed_runs"] = sorted(removed_set)


def _drop_matching_runs(
    mappings: Dict[str, Any],
    norm_run: Optional[str],
    norm_out: Optional[str],
    norm_doc: Optional[str],
    doc_base: Optional[str],
) -> None:
    """Removes the first matching run from each (optionally document-scoped) mapping entry."""
    for k, doc_entry in list(mappings.items()):
        if k.startswith("_") or not isinstance(doc_entry, dict):
            continue
        if norm_doc:
            entry_path = normalize_path(k)
            entry_file = normalize_path(str(doc_entry.get("file_path") or ""))
            entry_name = os.path.basename(entry_path)
            if norm_doc not in (entry_path, entry_file) and doc_base != entry_name:
                continue

        filtered = []
        removed_one = False
        for r in doc_entry.get("runs", []):
            r_id = normalize_path(str(r.get("run_id") or ""))
            r_dir = normalize_path(str(r.get("output_dir") or ""))
            is_match = (norm_run and r_id == norm_run) or (norm_out and r_dir == norm_out)
            if is_match and not removed_one:
                removed_one = True
                continue
            filtered.append(r)
        doc_entry["runs"] = filtered


def _delete_run_directory(root: str, target_dir_name: str) -> None:
    """Deletes a run output directory (never the shared "output" folder itself)."""
    norm_target = normalize_path(target_dir_name)
    candidates = [
        os.path.join(root, norm_target),
        os.path.join(root, "output", norm_target),
    ]
    for c_dir in candidates:
        if os.path.isdir(c_dir):
            rel = normalize_path(os.path.relpath(c_dir, root))
            if rel != "output":
                shutil.rmtree(c_dir, ignore_errors=True)


def _clean_root_output_for_document(
    root: str, norm_doc: str, doc_base: Optional[str]
) -> None:
    """Deletes root output artifacts if they reference the given document."""
    out_dir = os.path.join(root, "output")
    probe_files = ("plan.json", "plan_execution_result.json", "document_dom.json")
    should_clean = False
    for name in probe_files:
        fpath = os.path.join(out_dir, name)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            if (doc_base and doc_base in content) or norm_doc in content:
                should_clean = True
                break
        except OSError as ex:
            logger.debug("Failed to read %s: %s", fpath, ex)
    if not should_clean:
        return
    for art in _ROOT_OUTPUT_ARTIFACTS:
        _safe_remove(os.path.join(out_dir, art))
    for png in glob.glob(os.path.join(out_dir, "overlay_page_*.png")):
        _safe_remove(png)


def remove_run_mapping(
    run_id: str,
    output_dir: Optional[str] = None,
    document_path: Optional[str] = None,
    repo_root: Optional[str] = None,
) -> bool:
    """
    Removes a historical run from persistent mappings and deletes associated output artifacts.
    """
    root = repo_root or REPO_ROOT
    with _LOCK:
        mappings = load_persistent_mappings(root)

        norm_run = normalize_path(run_id) if run_id else None
        norm_out = normalize_path(output_dir) if output_dir else None
        norm_doc = normalize_path(document_path) if document_path else None
        doc_base = os.path.basename(norm_doc) if norm_doc else None

        _record_removal_keys(mappings, norm_run, norm_out, norm_doc, doc_base)
        _drop_matching_runs(mappings, norm_run, norm_out, norm_doc, doc_base)
        save_persistent_mappings(mappings, root)

        target_dir_name = output_dir or run_id
        if target_dir_name and target_dir_name != "output":
            _delete_run_directory(root, target_dir_name)
        elif target_dir_name == "output" and norm_doc:
            _clean_root_output_for_document(root, norm_doc, doc_base)

        return True


def get_file_run_mappings(
    repo_root: Optional[str] = None,
    available_docs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Synthesizes all discovered input documents, previous runs, and persistent
    mappings into a coherent hierarchical file-set -> document -> runs structure.
    """
    root = repo_root or REPO_ROOT
    with _LOCK:
        persistent_data = load_persistent_mappings(root)
        removed_runs: Set[str] = {
            normalize_path(str(x)) for x in _read_removed_keys(persistent_data) if x
        }

        discovered_runs = [r for r in find_previous_runs(root) if not _is_run_removed(r, removed_runs)]

        doc_paths = discover_document_paths(root, available_docs, persistent_data, discovered_runs)
        doc_mappings: Dict[str, Dict[str, Any]] = {
            d_path: _make_doc_entry(d_path, with_summary=True)
            for d_path in sorted(doc_paths)
        }

        associate_discovered_runs(doc_mappings, discovered_runs)
        merge_persistent_runs(doc_mappings, persistent_data, removed_runs)

        file_sets_list, all_mappings_list = group_into_file_sets(doc_mappings)
        active_doc, active_run = pick_active_selection(all_mappings_list)

        return {
            "file_sets": file_sets_list,
            "all_mappings": all_mappings_list,
            "total_documents": len(all_mappings_list),
            "total_runs": len(discovered_runs),
            "active_file": active_doc,
            "active_run": active_run,
        }
