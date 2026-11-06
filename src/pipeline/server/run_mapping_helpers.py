"""
src/pipeline/server/run_mapping_helpers.py

Pure helpers for normalizing paths and constructing run mapping records.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Set

EXCLUDED_DIR_NAMES: Set[str] = {
    "test_output",
    "test_output_server",
    "test_output_save",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}


def is_test_or_cache_dir(path: str) -> bool:
    """Returns True if any path segment matches banned test/cache directory names."""
    if not path or not path.strip():
        return False
    norm = normalize_path(path)
    parts = [p.lower() for p in norm.split("/") if p and p != "."]
    return any(p in EXCLUDED_DIR_NAMES for p in parts)


def is_excluded_path(path: str, repo_root: Optional[str] = None) -> bool:
    """
    Returns True if path points to test_output, build/cache directories,
    is a directory instead of a document file, or is not a valid PDF document.
    """
    if not path or not path.strip():
        return True
    norm = normalize_path(path)
    if is_test_or_cache_dir(norm):
        return True

    # Check filesystem status if root is provided or path is accessible
    check_path = os.path.join(repo_root, norm) if (repo_root and not os.path.isabs(norm)) else norm
    if os.path.exists(check_path) and os.path.isdir(check_path):
        return True

    if not norm.lower().endswith(".pdf"):
        return True

    return False


def normalize_path(path: str) -> str:
    """Normalizes path separators to standard forward slashes."""
    norm = path.replace("\\", "/").strip()
    while "//" in norm:
        norm = norm.replace("//", "/")
    if norm.startswith("./"):
        norm = norm[2:]
    return norm


def derive_file_set(rel_path: str) -> str:
    """Derives logical file set category from relative parent directory."""
    norm = normalize_path(rel_path)
    parts = [p for p in norm.split("/") if p and p != "."]
    if len(parts) > 1:
        # e.g. "src/e2e/doc.pdf" -> "e2e", "data/invoices/inv.pdf" -> "invoices"
        return parts[-2]
    return "workspace"


def make_doc_entry(file_path: str, file_name: Optional[str] = None, with_summary: bool = False) -> Dict[str, Any]:
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


def make_run_record(
    run_id: str,
    output_dir: str,
    preset: str,
    status: str,
    confidence: float,
    violations_count: int,
    total_pages: int,
    per_page_confidence: Optional[Dict[str, float]],
    per_page_violations: Optional[Dict[str, int]],
    timestamp: str,
) -> Dict[str, Any]:
    """Constructs the canonical run record shared by persisted and discovered runs."""
    return {
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
