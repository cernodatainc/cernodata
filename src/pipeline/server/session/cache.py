"""
src/pipeline/server/session/cache.py

Preset caching and previous run result lookup methods for server session context.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.pipeline.server.preset_cache import PresetCache


class PresetCacheMixin:
    """Mixin providing preset result caching and previous run disk lookups."""

    _lock: threading.RLock
    pdf_path: str
    repo_root: str
    current_result: Optional[Dict[str, Any]]
    _preset_cache: PresetCache

    def get_previous_runs(self) -> List[Dict[str, Any]]:
        """Method stub implemented by DocumentsMixin."""
        raise NotImplementedError

    def _make_cache_keys(self, pdf_path: str, preset: str, language: Optional[str] = None) -> List[str]:
        """Constructs canonical lookup keys delegating to PresetCache."""
        return self._preset_cache.make_cache_keys(pdf_path, preset, language)

    def get_cached_preset_result(
        self,
        pdf_path: str,
        preset: str,
        language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves previously computed or loaded pipeline result for a document and preset if available.
        Checks in-memory preset cache, current session result, and completed previous runs on disk.
        """
        with self._lock:
            # 1. In-memory cache check
            cached = self._preset_cache.get(pdf_path, preset, language)
            if cached is not None:
                return cached

            doc_base = os.path.basename(pdf_path).strip().lower() if pdf_path else ""
            preset_clean = preset.strip().lower() if preset else "docling_fast"

            # 2. Check if current_result matches requested preset and document
            if self.current_result:
                curr_dec = self.current_result.get("decision", {})
                curr_preset = (curr_dec.get("chosen_preset") or "").strip().lower()
                curr_doc = os.path.basename(self.pdf_path).strip().lower() if self.pdf_path else ""
                if curr_preset == preset_clean and (not doc_base or not curr_doc or curr_doc == doc_base):
                    return dict(self.current_result)

            # 3. Search completed previous runs in repository on disk
            return self._preset_cache.find_in_previous_runs(
                pdf_path=pdf_path,
                preset=preset,
                previous_runs=self.get_previous_runs(),
                repo_root=self.repo_root,
                language=language,
            )
