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


def get_mappings_file_path(repo_root: Optional[str] = None) -> str:
    """Returns absolute path to the persistent run_mappings.json store."""
    root = repo_root or REPO_ROOT
    out_dir = os.path.join(root, "output")
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, MAPPINGS_FILENAME)


def load_persistent_mappings(repo_root: Optional[str] = None) -> Dict[str, Any]:
    """Loads recorded file-to-run mappings from disk if present."""
    path = get_mappings_file_path(repo_root)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as ex:
        logger.warning("Failed to load run mappings from %s: %s", path, ex)
        return {}


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
    timestamp: str = "",
    repo_root: Optional[str] = None,
) -> None:
    """
    Records an execution run mapping for an input document and persists it to disk.
    """
    with _LOCK:
        mappings = load_persistent_mappings(repo_root)
        norm_path = normalize_path(document_path)
        doc_name = os.path.basename(norm_path)
        file_set = derive_file_set(norm_path)

        doc_entry = mappings.get(norm_path)
        if not doc_entry:
            doc_entry = {
                "file_path": norm_path,
                "file_name": doc_name,
                "file_set": file_set,
                "runs": [],
            }
            mappings[norm_path] = doc_entry

        run_record = {
            "run_id": run_id,
            "output_dir": output_dir,
            "preset": preset,
            "status": status,
            "overall_confidence": round(confidence, 4),
            "violations_count": violations_count,
            "total_pages": total_pages,
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
        discovered_runs = find_previous_runs(root)

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
                except Exception:
                    doc_paths.add(normalize_path(match))

        # Also include any documents previously recorded or found in runs
        for p_key in persistent_data.keys():
            norm_p = normalize_path(p_key)
            p_base = os.path.basename(norm_p)
            if not any(os.path.basename(p) == p_base for p in doc_paths):
                doc_paths.add(norm_p)

        for r in discovered_runs:
            d_path = r.get("document_path")
            if d_path:
                norm_d = normalize_path(d_path)
                d_base = os.path.basename(norm_d)
                if not any(os.path.basename(p) == d_base for p in doc_paths):
                    doc_paths.add(norm_d)

        # 2. Build mapping for each document
        doc_mappings: Dict[str, Dict[str, Any]] = {}
        for d_path in sorted(doc_paths):
            doc_name = os.path.basename(d_path)
            file_set = derive_file_set(d_path)
            doc_mappings[d_path] = {
                "file_path": d_path,
                "file_name": doc_name,
                "file_set": file_set,
                "runs": [],
                "runs_count": 0,
                "latest_run": None,
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
                matched_key = r_doc_path or r_doc_name
                doc_mappings[matched_key] = {
                    "file_path": matched_key,
                    "file_name": r_doc_name,
                    "file_set": derive_file_set(matched_key),
                    "runs": [],
                    "runs_count": 0,
                    "latest_run": None,
                }

            doc_entry = doc_mappings[matched_key]
            if not any(x["run_id"] == run_id for x in doc_entry["runs"]):
                doc_entry["runs"].append(run_entry)

        # 4. Integrate persistent records (if run folder was moved or archived)
        for p_path, p_val in persistent_data.items():
            norm_p = normalize_path(p_path)
            if norm_p in doc_mappings:
                target_runs = doc_mappings[norm_p]["runs"]
                for p_run in p_val.get("runs", []):
                    if not any(x["run_id"] == p_run.get("run_id") for x in target_runs):
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

        active_doc = all_mappings_list[0]["file_path"] if all_mappings_list else ""
        active_run = "output"
        if discovered_runs:
            active_run = str(discovered_runs[0].get("dir_path") or "output")

        return {
            "file_sets": file_sets_list,
            "all_mappings": all_mappings_list,
            "total_documents": len(all_mappings_list),
            "total_runs": len(discovered_runs),
            "active_file": active_doc,
            "active_run": active_run,
        }
