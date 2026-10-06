"""
src/pipeline/server/routes_static.py

Static asset routing, HTML template resolution, and web view delivery
for the cernodata pipeline viewer HTTP handler.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional

from src.pipeline.server.http_utils import (
    REPO_ROOT,
    SRC_DIR,
    send_file_response,
    send_first_existing_file,
    send_html_response,
)

if TYPE_CHECKING:
    from src.pipeline.server.session import ServerSessionContext


class StaticRoutesMixin:
    """
    Mixin providing static file, CSS/JS asset, and HTML page delivery
    for HTTP server request handlers.
    """

    server: Any

    @property
    def session(self) -> ServerSessionContext:
        """Session context provided by host request handler."""
        raise NotImplementedError

    def send_error(self, code: int, message: Optional[str] = None, explain: Optional[str] = None) -> None:
        """HTTP error sender stub satisfied by SimpleHTTPRequestHandler."""
        ...

    def _serve_landing_page(self) -> None:
        """
        Serves the interactive landing page and pipeline execution dashboard.
        Uses in-memory override from server instance if present.
        """
        html_override: str = getattr(self.server, "html_content", "")
        if html_override:
            send_html_response(self, html_override)  # type: ignore[arg-type]
            return

        landing_path = os.path.join(SRC_DIR, "visualization", "landing.html")
        if send_file_response(self, landing_path, "text/html; charset=utf-8"):  # type: ignore[arg-type]
            return
        self.send_error(500, "Landing page template not found")

    def _serve_viewer_html(self) -> None:
        """
        Serves the un-templated visual viewer HTML shell for client-side hydration.
        """
        candidates = [
            os.path.join(SRC_DIR, "visualization", "viewer", "viewer.html"),
            os.path.join(SRC_DIR, "visualization", "viewer", "template.html"),
        ]
        if not send_first_existing_file(self, candidates, "text/html; charset=utf-8"):  # type: ignore[arg-type]
            self.send_error(500, "Viewer template not found")

    def _serve_interactive_viewer_compat(self) -> None:
        """
        Serves backwards-compatible interactive viewer HTML from session output
        directory or global output directory.
        """
        candidates = [
            os.path.join(REPO_ROOT, self.session.output_dir or "output", "interactive_viewer.html"),
            os.path.join(REPO_ROOT, "output", "interactive_viewer.html"),
            os.path.join(SRC_DIR, "visualization", "viewer", "viewer.html"),
        ]
        if not send_first_existing_file(self, candidates, "text/html; charset=utf-8"):  # type: ignore[arg-type]
            self.send_error(404, "Interactive viewer not found")

    def _serve_data_shape_asset(self, filename: str, content_type: str, error_msg: str) -> None:
        """
        Serves data shape wizard asset from session output directory or fallback
        visualization source directory.

        Args:
            filename: Target asset filename.
            content_type: MIME Content-Type header string.
            error_msg: HTTP 404 error explanation if asset is missing.
        """
        candidates = [
            os.path.join(REPO_ROOT, self.session.output_dir or "output", filename),
            os.path.join(REPO_ROOT, "output", filename),
            os.path.join(SRC_DIR, "visualization", filename),
        ]
        if not send_first_existing_file(self, candidates, content_type):  # type: ignore[arg-type]
            self.send_error(404, error_msg)

    def _serve_planner_page(self) -> None:
        """
        Serves data shape questionnaire HTML configuration page.
        """
        html_override: str = getattr(self.server, "html_content", "")
        if html_override:
            send_html_response(self, html_override)  # type: ignore[arg-type]
            return
        self._serve_data_shape_asset("data_shape_config.html", "text/html; charset=utf-8", "Planner page not found")
