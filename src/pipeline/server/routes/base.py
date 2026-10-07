"""
src/pipeline/server/routes/base.py

Base mixin class and shared request utilities for server API route handlers.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from src.utils import resolve_pdf_path

if TYPE_CHECKING:
    from src.pipeline.server.session import ServerSessionContext

logger = logging.getLogger("cernodata.server.routes")


class BaseApiRoutesMixin:
    """Base mixin defining host server contracts and shared route utilities."""

    server: Any

    @property
    def session(self) -> ServerSessionContext:
        """Session context provided by host request handler."""
        raise NotImplementedError

    @property
    def executor(self) -> ThreadPoolExecutor:
        """Worker thread pool executor provided by host request handler."""
        raise NotImplementedError

    def send_error(self, code: int, message: Optional[str] = None, explain: Optional[str] = None) -> None:
        """HTTP error sender stub satisfied by SimpleHTTPRequestHandler."""
        ...

    def _extract_document_and_language(self, payload: Dict[str, Any]) -> Tuple[str, str]:
        """
        Extracts and resolves document path and language from request payload or session state.

        Args:
            payload: JSON request body dictionary.

        Returns:
            Tuple of (resolved_document_path, language_code).
        """
        raw_pdf = payload.get("pdf_path") or self.session.pdf_path or "src/e2e/Document 8.pdf"
        pdf_path = resolve_pdf_path(raw_pdf)
        language = payload.get("language") or self.session.language or "en"
        return pdf_path, language
