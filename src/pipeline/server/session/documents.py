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
                except Exception:
                    rel = match.replace("\\", "/")
                if rel not in docs:
                    docs.append(rel)
        with self._lock:
            if not docs and self.pdf_path:
                docs.append(self.pdf_path)
        return docs

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
