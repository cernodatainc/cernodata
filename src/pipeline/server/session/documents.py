"""
src/pipeline/server/session/documents.py

Document discovery, runs table grid retrieval, and previous run search for server sessions.
"""

from __future__ import annotations

import glob
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


class DocumentsMixin:
    """Mixin providing workspace document scanning, previous runs search, and runs grid."""

    _lock: threading.RLock
    pdf_path: str
    repo_root: str
    src_dir: str
    _registered_documents: List[str]

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
            elif not docs and self.pdf_path and not _is_forgotten(self.pdf_path) and not is_excluded_path(self.pdf_path, repo_root=self.repo_root):
                docs.append(self.pdf_path)
            elif self.pdf_path and self.pdf_path not in docs and not _is_forgotten(self.pdf_path) and not is_excluded_path(self.pdf_path, repo_root=self.repo_root):
                docs.append(self.pdf_path)
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
            try:
                if os.path.commonpath([self.repo_root, resolved]) == self.repo_root:
                    rel = os.path.relpath(resolved, self.repo_root).replace("\\", "/")
                else:
                    rel = resolved.replace("\\", "/")
            except ValueError:
                rel = resolved.replace("\\", "/")
        else:
            norm = path.strip().replace("\\", "/")
            try:
                if os.path.isabs(norm) and os.path.commonpath([self.repo_root, norm]) == self.repo_root:
                    rel = os.path.relpath(norm, self.repo_root).replace("\\", "/")
                else:
                    rel = norm
            except ValueError:
                rel = norm

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
        """Finds completed output runs available in repository."""
        return find_previous_runs(self.repo_root)

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
