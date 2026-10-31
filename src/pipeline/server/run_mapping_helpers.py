"""
src/pipeline/server/run_mapping_helpers.py

Pure helpers for normalizing paths and constructing run mapping records.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional


def normalize_path(path: str) -> str:
    """Normalizes path separators to standard forward slashes."""
    return path.replace("\\", "/").strip()


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
