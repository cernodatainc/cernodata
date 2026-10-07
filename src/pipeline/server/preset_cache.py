"""
src/pipeline/server/preset_cache.py

Thread-safe caching and retrieval of preset execution results
across in-memory state and workspace output directories.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

from src.pipeline.server.artifacts import load_run_artifacts

logger = logging.getLogger("cernodata.server.preset_cache")


class PresetCache:
    """
    Thread-safe storage and lookup index for preset pipeline results.

    Enables instant reuse of previously executed extractions for matching
    document paths, presets, and language options without redundant OCR inference.
    """

    def __init__(self, lock: Optional[threading.RLock] = None) -> None:
        self._lock: threading.RLock = lock if lock is not None else threading.RLock()
        self.preset_results: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def make_cache_keys(pdf_path: str, preset: str, language: Optional[str] = None) -> List[str]:
        """
        Constructs canonical lookup keys for caching preset runs.

        Args:
            pdf_path: Filesystem path to document.
            preset: Extraction preset name.
            language: Optional language hint code.

        Returns:
            List of hierarchical lookup keys ordered from most to least specific.
        """
        doc_base = os.path.basename(pdf_path).strip().lower() if pdf_path else ""
        preset_clean = preset.strip().lower() if preset else "docling_fast"
        keys: List[str] = []
        if doc_base:
            keys.append(f"{doc_base}:{preset_clean}")
            if language:
                keys.insert(0, f"{doc_base}:{preset_clean}:{language.strip().lower()}")
        keys.append(preset_clean)
        return keys

    def get(self, pdf_path: str, preset: str, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves a cached preset result from memory if present.

        Args:
            pdf_path: Source document path.
            preset: Extraction preset identifier.
            language: Optional language hint code.

        Returns:
            Cached result dictionary or None.
        """
        with self._lock:
            for k in self.make_cache_keys(pdf_path, preset, language):
                if k in self.preset_results:
                    return dict(self.preset_results[k])
            return None

    def put(
        self,
        pdf_path: str,
        preset: str,
        result: Dict[str, Any],
        language: Optional[str] = None,
        candidate_paths: Optional[List[str]] = None,
    ) -> None:
        """
        Stores a pipeline result under canonical cache keys for the specified document.

        Args:
            pdf_path: Primary source document path.
            preset: Extraction preset identifier.
            result: Result dictionary to cache.
            language: Optional language hint code.
            candidate_paths: Optional additional document paths/aliases to index.
        """
        with self._lock:
            keys_to_cache = self.make_cache_keys(pdf_path, preset, language)
            if candidate_paths:
                for cand in candidate_paths:
                    keys_to_cache.extend(self.make_cache_keys(cand, preset, language))
            cached_copy = dict(result)
            for k in keys_to_cache:
                self.preset_results[k] = cached_copy

    def find_in_previous_runs(
        self,
        pdf_path: str,
        preset: str,
        previous_runs: List[Dict[str, Any]],
        repo_root: str,
        language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Searches discovered output runs on disk for a matching document and preset,
        loading artifacts and updating the in-memory cache if found.

        Args:
            pdf_path: Source document path.
            preset: Extraction preset identifier.
            previous_runs: List of discovered previous run metadata dictionaries.
            repo_root: Absolute repository root directory.
            language: Optional language hint code.

        Returns:
            Loaded result dictionary or None.
        """
        doc_base = os.path.basename(pdf_path).strip().lower() if pdf_path else ""
        preset_clean = preset.strip().lower() if preset else "docling_fast"
        target_keys = self.make_cache_keys(pdf_path, preset, language)

        for r in previous_runs:
            r_doc = os.path.basename(r.get("document_path") or r.get("document_name") or "").strip().lower()
            r_preset = (r.get("chosen_preset") or "").strip().lower()
            if (not doc_base or r_doc == doc_base) and r_preset == preset_clean:
                dir_path = r.get("dir_path")
                if dir_path:
                    full_dir = dir_path if os.path.isabs(dir_path) else os.path.join(repo_root, dir_path)
                    artifacts = load_run_artifacts(full_dir)
                    if artifacts.dom and artifacts.decision:
                        res: Dict[str, Any] = {
                            "dom": artifacts.dom,
                            "decision": artifacts.decision,
                            "violations": artifacts.violations,
                            "plan": artifacts.plan,
                        }
                        with self._lock:
                            for k in target_keys:
                                self.preset_results[k] = res
                        return res

        return None
