"""
src/pipeline/server/routes/base.py

Base mixin class and shared request utilities for server API route handlers.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from src.pipeline.planner import PresetPlanner
from src.pipeline.server.http_utils import send_json_response
from src.utils import resolve_pdf_path

if TYPE_CHECKING:
    from src.pipeline.server.core import PipelineViewerServer
    from src.pipeline.server.session import ServerSessionContext

logger = logging.getLogger("cernodata.server.routes")


class BaseApiRoutesMixin:
    """Base mixin defining host server contracts and shared route utilities."""

    server: PipelineViewerServer

    @property
    def session(self) -> ServerSessionContext:
        """Session context provided by host request handler."""
        raise NotImplementedError

    @property
    def executor(self) -> ThreadPoolExecutor:
        """Worker thread pool executor provided by host request handler."""
        raise NotImplementedError

    def _get_active_planner(self) -> PresetPlanner:
        """Returns the server's active PresetPlanner with custom presets loaded if present."""
        existing = self.server.planner
        if existing is not None:
            return existing
        custom_path = self.server.custom_presets_path
        if not custom_path:
            out_dir = self.server.output_dir or "output"
            custom_path = os.path.join(out_dir, "custom_presets.json")
        if custom_path and os.path.isfile(custom_path):
            return PresetPlanner(custom_presets_path=custom_path)
        return PresetPlanner()

    if TYPE_CHECKING:
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

    def _resolve_document_and_language(
        self,
        raw_pdf: Optional[str],
        raw_lang: Optional[str],
    ) -> Tuple[str, str]:
        """Resolves document path and language code from validated inputs or active session state."""
        target_pdf = raw_pdf or self.session.pdf_path or self.server.default_doc
        if not target_pdf:
            raise ValueError("No document path provided in request payload or active session.")

        pdf_path = resolve_pdf_path(target_pdf)
        cleaned_lang = raw_lang
        if isinstance(cleaned_lang, str) and cleaned_lang.strip().lower() in ("auto", "none", ""):
            cleaned_lang = None
        language = cleaned_lang or self.session.language or "en"
        if isinstance(language, str) and language.strip().lower() in ("auto", "none", ""):
            language = "en"
        return pdf_path, str(language)

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
        return self._resolve_document_and_language(
            raw_pdf=payload.get("pdf_path"),
            raw_lang=payload.get("language"),
        )
