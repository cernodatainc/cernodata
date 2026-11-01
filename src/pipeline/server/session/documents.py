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
from src.pipeline.server.run_mappings import get_file_run_mappings, register_document_path


class DocumentsMixin:
    """Mixin providing workspace document scanning, previous runs search, and runs grid."""

    _lock: threading.RLock
    pdf_path: str
    repo_root: str
    src_dir: str

    def get_available_documents(self) -> List[str]:
        """Finds candidate PDF documents in repository workspace."""
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
                if rel not in docs:
                    docs.append(rel)
        with self._lock:
            for reg in getattr(self, "_registered_documents", []):
                if reg not in docs:
                    docs.append(reg)
            if not docs and self.pdf_path:
                docs.append(self.pdf_path)
            elif self.pdf_path and self.pdf_path not in docs:
                docs.append(self.pdf_path)
        return docs

    def register_document(self, path: str) -> str:
        """
        Registers a document path with the session without uploading or copying the file.
        Makes the path known to discovery, active session, and persistent mappings.
        """
        norm = path.strip().replace("\\", "/")
        try:
            if os.path.isabs(norm) and os.path.commonpath([self.repo_root, norm]) == self.repo_root:
                rel = os.path.relpath(norm, self.repo_root).replace("\\", "/")
            else:
                rel = norm
        except ValueError:
            rel = norm

        with self._lock:
            if not hasattr(self, "_registered_documents"):
                self._registered_documents: List[str] = []
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
