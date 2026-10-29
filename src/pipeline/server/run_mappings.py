"""
src/pipeline/server/run_mappings.py

Persistent mapping repository and discovery service linking input document files
and file sets to historical pipeline parsing runs.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Set

from src.pipeline.server.discovery import find_previous_runs
from src.pipeline.server.http_utils import REPO_ROOT
from src.utils import safe_load_json

logger = logging.getLogger("cernodata.server.run_mappings")

_LOCK = threading.RLock()
MAPPINGS_FILENAME = "run_mappings.json"


def normalize_path(path: str) -> str:
    """Normalizes path separators to standard forward slashes."""
    return path.replace("\\", "/").strip()


def derive_file_set(rel_path: str) -> str:
    """Derives logical file set category from relative parent directory."""
    norm = normalize_path(rel_path)
    parts = norm.split("/")
    if len(parts) > 1:
        # e.g. "src/e2e/doc.pdf" -> "e2e", "data/invoices/inv.pdf" -> "invoices"
        return parts[-2]
    return "workspace"


def _safe_remove(path: str) -> None:
    """Removes a file if it exists, logging (not raising) on OS errors."""
    if not os.path.isfile(path):
        return
    try:
        os.remove(path)
    except OSError as ex:
        logger.debug("Failed to remove %s: %s", path, ex)


def _make_doc_entry(file_path: str, file_name: Optional[str] = None, with_summary: bool = False) -> Dict[str, Any]:
    """Constructs a canonical document mapping dictionary."""
    entry: Dict[str, Any] = {
        "file_path": file_path,
        "file_name": file_name or os.path.basename(file_path),
        "file_set": derive_file_set(file_path),
        "runs": [],
    }
    if with_summary:
        entry["runs_count"] = 0
        entry["latest_run"] = None
    return entry


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

        run_record = {
            "run_id": run_id,
            "output_dir": output_dir,
            "preset": preset,
            "status": status,
            "overall_confidence": round(confidence, 4),
            "violations_count": violations_count,
            "total_pages": total_pages,
            "per_page_confidence": per_page_confidence or {},
            "per_page_violations": per_page_violations or {},
            "timestamp": timestamp,
        }

        # Avoid duplicates for same run_id
        existing_runs = doc_entry.get("runs", [])
        idx = next((i for i, r in enumerate(existing_runs) if r.get("run_id") == run_id), None)
        if idx is not None:
            existing_runs[idx] = run_record
        else:
            existing_runs.append(run_record)

        doc_entry["runs"] = existing_runs
        save_persistent_mappings(mappings, repo_root)


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
        removed_list = mappings.get("_removed_runs", [])
        if not isinstance(removed_list, list):
            removed_list = []
        removed_set = set(removed_list)

        norm_run = normalize_path(run_id) if run_id else None
        norm_out = normalize_path(output_dir) if output_dir else None
        norm_doc = normalize_path(document_path) if document_path else None
        doc_base = os.path.basename(norm_doc) if norm_doc else None

        # Record specific removal keys without suppressing the shared "output" folder
        for item in (norm_run, norm_out):
            if item and item != "output":
                removed_set.add(item)
            elif item == "output" and norm_doc:
                removed_set.add(f"{norm_doc}::{item}")
                if doc_base:
                    removed_set.add(f"{doc_base}::{item}")
        mappings["_removed_runs"] = sorted(removed_set)

        for k, doc_entry in list(mappings.items()):
            if k.startswith("_") or not isinstance(doc_entry, dict):
                continue
            if norm_doc:
                entry_path = normalize_path(k)
                entry_file = normalize_path(str(doc_entry.get("file_path") or ""))
                entry_name = os.path.basename(entry_path)
                if norm_doc not in (entry_path, entry_file) and doc_base != entry_name:
                    continue

            runs = doc_entry.get("runs", [])
            filtered = []
            removed_one = False
            for r in runs:
                r_id = normalize_path(str(r.get("run_id") or ""))
                r_dir = normalize_path(str(r.get("output_dir") or ""))
                is_match = (norm_run and r_id == norm_run) or (norm_out and r_dir == norm_out)
                if is_match and not removed_one:
                    removed_one = True
                    continue
                filtered.append(r)
            doc_entry["runs"] = filtered

        save_persistent_mappings(mappings, root)

        target_dir_name = output_dir or run_id
        if target_dir_name and target_dir_name != "output":
            norm_target = normalize_path(target_dir_name)
            candidates = [
                os.path.join(root, norm_target),
                os.path.join(root, "output", norm_target),
            ]
            for c_dir in candidates:
                if os.path.isdir(c_dir):
                    rel = normalize_path(os.path.relpath(c_dir, root))
                    if rel != "output":
                        import shutil
                        shutil.rmtree(c_dir, ignore_errors=True)
        elif target_dir_name == "output" and norm_doc:
            out_dir = os.path.join(root, "output")
            plan_path = os.path.join(out_dir, "plan.json")
            res_path = os.path.join(out_dir, "plan_execution_result.json")
            dom_path = os.path.join(out_dir, "document_dom.json")
            should_clean = False
            for fpath in (plan_path, res_path, dom_path):
                if os.path.isfile(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            content = f.read()
                            if (doc_base and doc_base in content) or norm_doc in content:
                                should_clean = True
                                break
                    except OSError as ex:
                        logger.debug("Failed to read %s: %s", fpath, ex)
            if should_clean:
                for art in (
                    "plan_execution_result.json",
                    "document_dom.json",
                    "plan.json",
                    "interactive_viewer.html",
                    "quality_violations.json",
                ):
                    _safe_remove(os.path.join(out_dir, art))
                for png in glob.glob(os.path.join(out_dir, "overlay_page_*.png")):
                    _safe_remove(png)

        return True


def _is_run_removed(r: Dict[str, Any], removed_runs: Set[str]) -> bool:
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
        raw_removed = persistent_data.get("_removed_runs", [])
        if not isinstance(raw_removed, list):
            raw_removed = []
        removed_runs: Set[str] = {normalize_path(str(x)) for x in raw_removed if x}

        discovered_runs = [r for r in find_previous_runs(root) if not _is_run_removed(r, removed_runs)]

        # 1. Discover all candidate PDF files
        doc_paths: Set[str] = set()
        if available_docs:
            doc_paths.update(normalize_path(d) for d in available_docs)

        for pat in [
            os.path.join(root, "src", "e2e", "*.pdf"),
            os.path.join(root, "output", "*.pdf"),
            os.path.join(root, "*.pdf"),
        ]:
            for match in glob.glob(pat):
                try:
                    rel = os.path.relpath(match, root)
                    doc_paths.add(normalize_path(rel))
                except ValueError:
                    doc_paths.add(normalize_path(match))

        # Also include any documents previously recorded or found in runs
        for p_key, p_val in persistent_data.items():
            if p_key.startswith("_") or not isinstance(p_val, dict):
                continue
            norm_p = normalize_path(p_key)
            p_base = os.path.basename(norm_p)
            if not any(os.path.basename(p) == p_base for p in doc_paths):
                doc_paths.add(norm_p)

        for r in discovered_runs:
            d_path = r.get("document_path")
            if d_path and not d_path.startswith("_"):
                norm_d = normalize_path(d_path)
                d_base = os.path.basename(norm_d)
                if not any(os.path.basename(p) == d_base for p in doc_paths):
                    doc_paths.add(norm_d)

        # 2. Build mapping for each document
        doc_mappings: Dict[str, Dict[str, Any]] = {
            d_path: _make_doc_entry(d_path, with_summary=True)
            for d_path in sorted(doc_paths)
        }

        # Helper to find matching document key by path or base filename
        def _match_doc_key(target: str) -> Optional[str]:
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

        # 3. Associate runs with documents
        for r in discovered_runs:
            r_doc_path = normalize_path(r.get("document_path") or "")
            r_doc_name = r.get("document_name") or os.path.basename(r_doc_path)
            run_id = r.get("id") or r.get("dir_path") or "output"
            output_dir = r.get("dir_path") or "output"
            preset = r.get("chosen_preset") or "docling_fast"
            status = r.get("status") or "ACCEPT"
            conf = float(r.get("overall_confidence", 1.0))
            viols = int(r.get("violations_count", 0))
            pages = int(r.get("total_pages", 1))
            t_stamp = r.get("timestamp") or ""

            run_entry = {
                "run_id": run_id,
                "output_dir": output_dir,
                "preset": preset,
                "status": status,
                "overall_confidence": round(conf, 4),
                "violations_count": viols,
                "total_pages": pages,
                "per_page_confidence": r.get("per_page_confidence", {}),
                "per_page_violations": r.get("per_page_violations", {}),
                "timestamp": t_stamp,
                "has_viewer": r.get("has_viewer", False),
                "has_dom": r.get("has_dom", False),
                "has_plan": r.get("has_plan", False),
                "label": r.get("label", ""),
            }

            # Find matching document
            matched_key = _match_doc_key(r_doc_path) or _match_doc_key(r_doc_name)

            if not matched_key:
                # Document wasn't pre-discovered on disk, create entry for it
                candidate_key = r_doc_path or r_doc_name
                if candidate_key and not candidate_key.startswith("_"):
                    matched_key = candidate_key
                    doc_mappings[matched_key] = _make_doc_entry(
                        matched_key, file_name=r_doc_name, with_summary=True
                    )

            if matched_key:
                doc_entry = doc_mappings[matched_key]
                if not any(x["run_id"] == run_id for x in doc_entry["runs"]):
                    doc_entry["runs"].append(run_entry)

        # 4. Integrate persistent records (if run folder was moved or archived)
        for p_path, p_val in persistent_data.items():
            if p_path.startswith("_") or not isinstance(p_val, dict):
                continue
            norm_p = normalize_path(p_path)
            if norm_p in doc_mappings:
                target_runs = doc_mappings[norm_p]["runs"]
                for p_run in p_val.get("runs", []):
                    r_id = p_run.get("run_id")
                    r_out = p_run.get("output_dir")
                    if r_id in removed_runs or r_out in removed_runs:
                        continue
                    if not any(x["run_id"] == r_id for x in target_runs):
                        target_runs.append(p_run)

        # 5. Finalize summaries and group into file sets
        file_sets_map: Dict[str, Dict[str, Any]] = {}
        all_mappings_list: List[Dict[str, Any]] = []

        for d_path, entry in doc_mappings.items():
            runs_list = entry["runs"]
            # Sort runs: output first, then by run_id
            runs_list.sort(key=lambda x: (x["output_dir"] != "output", x["run_id"]))
            entry["runs_count"] = len(runs_list)
            entry["latest_run"] = runs_list[0] if runs_list else None
            all_mappings_list.append(entry)

            f_set = entry["file_set"]
            if f_set not in file_sets_map:
                file_sets_map[f_set] = {
                    "file_set": f_set,
                    "document_count": 0,
                    "runs_count": 0,
                    "documents": [],
                }
            file_sets_map[f_set]["documents"].append(entry)
            file_sets_map[f_set]["document_count"] += 1
            file_sets_map[f_set]["runs_count"] += len(runs_list)

        file_sets_list = sorted(file_sets_map.values(), key=lambda s: str(s["file_set"]))

        active_doc = ""
        active_run = ""
        for entry in all_mappings_list:
            if entry.get("runs"):
                active_doc = str(entry["file_path"])
                latest = entry.get("latest_run") or entry["runs"][0]
                active_run = str(latest.get("output_dir") or latest.get("run_id") or "")
                break

        if not active_doc and all_mappings_list:
            active_doc = str(all_mappings_list[0]["file_path"])
            active_run = ""

        return {
            "file_sets": file_sets_list,
            "all_mappings": all_mappings_list,
            "total_documents": len(all_mappings_list),
            "total_runs": len(discovered_runs),
            "active_file": active_doc,
            "active_run": active_run,
        }
