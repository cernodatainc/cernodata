"""
src/pipeline/server/routes/config.py

Configuration and run retrieval API endpoints for cernodata HTTP server.
"""

from __future__ import annotations

from typing import Any, Dict, List
from src.pipeline.planner.options import (
    DEFAULT_PRESET_WEIGHTS,
    SECURITY_OPTIONS,
    TARGET_OPTIONS,
    TAXONOMY_OPTIONS,
    WIZARD_DIMENSIONS,
)
from src.quality.layers import ALL_VERIFICATION_LAYERS, DEFAULT_VERIFICATION_LAYERS, LAYER_METADATA
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

    def _get_custom_presets_catalog(self) -> List[Dict[str, Any]]:
        """No-op hook returning custom OCR presets and community recipes for the Web Hub UI."""
        # TODO(TASK-207): Return user-saved CustomPresetConfig entries and community OCR recipes (TASK-208)
        # to populate the guided 'Add / Connect Custom OCR Preset' modal in the Web Hub.
        return []

    def _get_ollama_models_status(self) -> Dict[str, Any]:
        """No-op hook returning local Ollama availability and installed models for the Web UI."""
        # TODO(TASK-406): Check local Ollama availability via OllamaClient (TASK-401) and return installed
        # model names so the Web Hub and Viewer can populate the Local AI Assistant dropdown.
        return {"available": False, "models": []}

    def _get_template_hints_catalog(self) -> List[Dict[str, Any]]:
        """No-op hook returning available spatial document layout templates for the Web Hub UI."""
        # TODO(TASK-903): Return starter (TASK-905) and user-saved (TASK-904) DocumentTemplateHint options
        # for the 'Document Layout Template' dropdown in the Web Hub.
        return []

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
            "dimensions": [d.to_dict() for d in WIZARD_DIMENSIONS],
            "taxonomy_options": TAXONOMY_OPTIONS,
            "target_options": TARGET_OPTIONS,
            "security_options": SECURITY_OPTIONS,
            "previous_runs": self.session.get_previous_runs(),
            "active_run": self.session.output_dir,
            "verification_layers": ALL_VERIFICATION_LAYERS,
            "default_verification_layers": DEFAULT_VERIFICATION_LAYERS,
            "verification_layer_metadata": LAYER_METADATA,
            "custom_presets": self._get_custom_presets_catalog(),
            "ollama_status": self._get_ollama_models_status(),
            "template_hints": self._get_template_hints_catalog(),
        })
