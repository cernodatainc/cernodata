"""
src/pipeline/server/session/documents.py

Document discovery, runs table grid retrieval, and previous run search for server sessions.
"""

from __future__ import annotations

import glob
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from src.pipeline.server.discovery import build_runs_grid, find_previous_runs
from src.pipeline.server.run_mapping_helpers import is_excluded_path
from src.pipeline.server.run_mappings import (
    _read_forgotten_files,
    forget_document as _forget_doc,
    get_file_run_mappings,
    load_persistent_mappings,
    normalize_path,
    register_document_path,
)

logger = logging.getLogger("cernodata.server.session.documents")


class DocumentsMixin:
    """Mixin providing workspace document scanning, previous runs search, and runs grid."""

    _lock: threading.RLock
    pdf_path: str
    repo_root: str
    src_dir: str
    _registered_documents: List[str]

    def _to_repo_relative(self, path_str: str) -> str:
        """Converts path_str to a forward-slash path relative to repo_root when inside it."""
        if not path_str:
            return ""
        abs_root = os.path.abspath(self.repo_root)
        abs_target = os.path.abspath(path_str) if os.path.isabs(path_str) else os.path.abspath(os.path.join(abs_root, path_str))
        try:
            if os.path.commonpath([os.path.normcase(abs_root), os.path.normcase(abs_target)]) == os.path.normcase(abs_root):
                return os.path.relpath(abs_target, abs_root).replace("\\", "/")
        except ValueError as ex:
            logger.debug("Skipping repo relativization for cross-drive path '%s': %s", path_str, ex)
        return abs_target.replace("\\", "/") if os.path.isabs(path_str) else path_str.replace("\\", "/")

    def get_available_documents(self) -> List[str]:
        """Finds candidate PDF documents in repository workspace."""
        persistent_data = load_persistent_mappings(self.repo_root)
        forgotten_set = {normalize_path(str(x)) for x in _read_forgotten_files(persistent_data) if x}

        def _is_forgotten(path_str: str) -> bool:
            if not path_str or not forgotten_set:
                return False
            norm = normalize_path(path_str)
            return norm in forgotten_set or os.path.basename(norm) in forgotten_set

        docs: List[str] = []
        for pat in [
            os.path.join(self.repo_root, "src", "e2e", "*.pdf"),
            os.path.join(self.repo_root, "output", "*.pdf"),
            os.path.join(self.repo_root, "*.pdf"),
            os.path.join(self.src_dir, "e2e", "*.pdf"),
        ]:
            for match in glob.glob(pat):
                try:
                    rel = os.path.relpath(match, self.repo_root).replace("\\", "/")
                except ValueError:
                    rel = match.replace("\\", "/")
                if rel not in docs and not _is_forgotten(rel) and not is_excluded_path(rel, repo_root=self.repo_root):
                    docs.append(rel)
        with self._lock:
            for reg in getattr(self, "_registered_documents", []):
                if reg not in docs and not _is_forgotten(reg) and not is_excluded_path(reg, repo_root=self.repo_root):
                    docs.append(reg)
            if self.pdf_path and _is_forgotten(self.pdf_path):
                self.pdf_path = docs[0] if docs else ""
            elif self.pdf_path:
                norm_active = self._to_repo_relative(self.pdf_path)
                if not _is_forgotten(norm_active) and not is_excluded_path(norm_active, repo_root=self.repo_root):
                    if not docs or (norm_active not in docs and not any(os.path.basename(d).lower() == os.path.basename(norm_active).lower() for d in docs)):
                        docs.append(norm_active)
        return docs

    def forget_document(self, path: str) -> bool:
        """
        Marks a document as forgotten so it disappears from the explorer without deleting past runs.
        """
        norm = normalize_path(path)
        with self._lock:
            if hasattr(self, "_registered_documents"):
                self._registered_documents = [
                    d for d in self._registered_documents
                    if normalize_path(d) != norm and os.path.basename(d) != os.path.basename(norm)
                ]
            if normalize_path(self.pdf_path) == norm or os.path.basename(self.pdf_path) == os.path.basename(norm):
                self.pdf_path = ""
        return _forget_doc(norm, repo_root=self.repo_root)

    def register_document(self, path: str) -> str:
        """
        Registers a document path with the session without uploading or copying the file.
        Makes the path known to discovery, active session, and persistent mappings.
        Automatically unforget the document if it was previously forgotten.
        """
        if not path or not path.strip() or is_excluded_path(path, repo_root=self.repo_root):
            return ""

        from src.utils import resolve_pdf_path

        resolved = resolve_pdf_path(path)
        if os.path.isdir(resolved):
            return ""

        if os.path.exists(resolved):
            rel = self._to_repo_relative(resolved)
        else:
            norm = path.strip().replace("\\", "/")
            rel = self._to_repo_relative(norm) if os.path.isabs(norm) else norm

        if is_excluded_path(rel, repo_root=self.repo_root):
            return ""

        with self._lock:
            if not hasattr(self, "_registered_documents"):
                self._registered_documents = []
            if rel not in self._registered_documents:
                self._registered_documents.append(rel)
            self.pdf_path = rel

        register_document_path(rel, repo_root=self.repo_root)
        return rel

    def get_previous_runs(self) -> List[Dict[str, Any]]:
        """Finds completed output runs available in repository, excluding removed runs."""
        from src.pipeline.server.run_mapping_synthesis import is_run_removed
        from src.pipeline.server.run_mappings import _read_removed_keys

        persistent_data = load_persistent_mappings(self.repo_root)
        removed_runs = {
            normalize_path(str(x)) for x in _read_removed_keys(persistent_data) if x
        }
        runs = find_previous_runs(self.repo_root)
        if not removed_runs:
            return runs
        return [r for r in runs if not is_run_removed(r, removed_runs)]

    def get_runs_grid(self, document_name: Optional[str] = None) -> Dict[str, Any]:
        """Thread-safe retrieval of previous runs table grid for a given document."""
        with self._lock:
            runs = self.get_previous_runs()
            target = document_name
            if not target and self.pdf_path:
                target = os.path.basename(self.pdf_path)
            return build_runs_grid(runs, target_file=target)

    def get_file_run_mappings(self) -> Dict[str, Any]:
        """Thread-safe retrieval of input files and historical parsing run mappings."""
        with self._lock:
            docs = self.get_available_documents()
            return get_file_run_mappings(self.repo_root, available_docs=docs)
