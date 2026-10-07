"""
src/pipeline/server/routes/config.py

Configuration and run retrieval API endpoints for cernodata HTTP server.
"""

from __future__ import annotations

from src.pipeline.planner_options import (
    DEFAULT_PRESET_WEIGHTS,
    SECURITY_OPTIONS,
    TARGET_OPTIONS,
    TAXONOMY_OPTIONS,
    WIZARD_DIMENSIONS,
)
from src.pipeline.server.http_utils import send_json_response
from src.pipeline.server.routes.base import BaseApiRoutesMixin


class ConfigRoutesMixin(BaseApiRoutesMixin):
    """Mixin handling configuration retrieval and previous run loading endpoints."""

    def _handle_load_run(self, target_dir: str) -> None:
        """
        Executes run loading and sends standard response.

        Args:
            target_dir: Target output directory path to load into session.
        """
        if not target_dir:
            send_json_response(self, 400, {"success": False, "error": "Missing output_dir parameter"})  # type: ignore[arg-type]
            return
        loaded = self.session.load_previous_run(target_dir)
        send_json_response(self, 200, {  # type: ignore[arg-type]
            "success": True,
            "output_dir": self.session.output_dir,
            "run": loaded,
            "results": self.session.get_results(),
        })

    def _handle_api_config(self) -> None:
        """
        Returns runtime server configuration and preset options.
        """
        configured_doc = getattr(self.server, "default_doc", None)
        session_doc = self.session.pdf_path
        default_doc = configured_doc or session_doc or ""
        default_lang = getattr(self.server, "default_lang", None) or self.session.language or "en"
        default_thresh = getattr(self.server, "default_threshold", 0.85)

        send_json_response(self, 200, {  # type: ignore[arg-type]
            "default_doc": default_doc,
            "default_lang": default_lang,
            "default_threshold": default_thresh,
            "preset_weights": DEFAULT_PRESET_WEIGHTS,
            "dimensions": [
                {
                    "key": d.key,
                    "title": d.title,
                    "description": d.description,
                    "options": d.options,
                    "default": d.default,
                }
                for d in WIZARD_DIMENSIONS
            ],
            "taxonomy_options": TAXONOMY_OPTIONS,
            "target_options": TARGET_OPTIONS,
            "security_options": SECURITY_OPTIONS,
            "previous_runs": self.session.get_previous_runs(),
            "active_run": self.session.output_dir,
        })
