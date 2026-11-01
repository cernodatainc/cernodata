"""
src/pipeline/server/routes/base.py

Base mixin class and shared request utilities for server API route handlers.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from src.pipeline.server.http_utils import send_json_response
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

    def send_ok(self, data: Optional[Dict[str, Any]] = None, **extra: Any) -> None:
        """Sends a 200 OK JSON response with success: True."""
        body: Dict[str, Any] = {"success": True}
        if data:
            body.update(data)
        if extra:
            body.update(extra)
        send_json_response(self, 200, body)  # type: ignore[arg-type]

    def send_bad_request(self, message: str, **extra: Any) -> None:
        """Sends a 400 Bad Request JSON response with success: False."""
        body: Dict[str, Any] = {"success": False, "error": message}
        if extra:
            body.update(extra)
        send_json_response(self, 400, body)  # type: ignore[arg-type]

    def send_server_error(self, message: str, **extra: Any) -> None:
        """Sends a 500 Internal Server Error JSON response with success: False."""
        body: Dict[str, Any] = {"success": False, "error": message}
        if extra:
            body.update(extra)
        send_json_response(self, 500, body)  # type: ignore[arg-type]

    def send_json(self, status_code: int, data: Dict[str, Any]) -> None:
        """Sends a JSON response with the specified HTTP status code."""
        send_json_response(self, status_code, data)  # type: ignore[arg-type]

    def _extract_document_and_language(self, payload: Dict[str, Any]) -> Tuple[str, str]:
        """
        Extracts and resolves document path and language from request payload or session state.

        Args:
            payload: JSON request body dictionary.

        Returns:
            Tuple of (resolved_document_path, language_code).

        Raises:
            ValueError: If no document path is provided in payload or session.
        """
        raw_pdf = payload.get("pdf_path") or self.session.pdf_path
        if not raw_pdf:
            default_doc = getattr(self.server, "default_doc", None)
            if default_doc:
                raw_pdf = default_doc
            else:
                raise ValueError("No document path provided in request payload or active session.")

        pdf_path = resolve_pdf_path(raw_pdf)
        raw_lang = payload.get("language")
        if isinstance(raw_lang, str) and raw_lang.strip().lower() in ("auto", "none", ""):
            raw_lang = None
        language = raw_lang or self.session.language or "en"
        if isinstance(language, str) and language.strip().lower() in ("auto", "none", ""):
            language = "en"
        return pdf_path, str(language)
