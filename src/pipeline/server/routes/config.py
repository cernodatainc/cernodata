"""
src/pipeline/server/routes/config.py

Configuration and run retrieval API endpoints for cernodata HTTP server.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, List, Optional
from src.pipeline.planner.options import (
    DEFAULT_PRESET_WEIGHTS,
    SECURITY_OPTIONS,
    TARGET_OPTIONS,
    TAXONOMY_OPTIONS,
    WIZARD_DIMENSIONS,
)
from src.quality.layers import ALL_VERIFICATION_LAYERS, DEFAULT_VERIFICATION_LAYERS, LAYER_METADATA
from src.pipeline.server.http_utils import send_json_response
from src.pipeline.server.routes.base import BaseApiRoutesMixin, logger


def open_system_file_dialog(mock_paths: Optional[List[str]] = None) -> List[str]:
    """
    Opens the OS native File Explorer window to let the user select PDF documents.
    Returns list of chosen file paths without uploading any file contents.
    """
    if mock_paths is not None:
        return list(mock_paths)

    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CI"):
        return []

    if sys.platform == "win32":
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$f = New-Object System.Windows.Forms.OpenFileDialog; "
            "$f.Multiselect = $true; "
            "$f.Filter = 'PDF Files (*.pdf)|*.pdf|All Files (*.*)|*.*'; "
            "$f.Title = 'Select PDF Documents'; "
            "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
            "    $f.FileNames | ForEach-Object { Write-Output $_ } "
            "}"
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if res.returncode == 0 and res.stdout:
                paths = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                return paths
            return []
        except Exception as e:
            logger.warning("PowerShell file explorer dialog failed: %s", e)
            return []
    return []


class ConfigRoutesMixin(BaseApiRoutesMixin):
    """Mixin handling configuration retrieval and previous run loading endpoints."""

    _mock_dialog_paths: Optional[List[str]] = None

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

    def _handle_post_open_file_dialog(self, payload: Dict[str, Any]) -> None:
        """
        Opens the system native File Explorer window to select documents,
        making their paths known to the backend without uploading files.
        """
        paths = open_system_file_dialog(self._mock_dialog_paths)
        if not paths:
            send_json_response(self, 200, {  # type: ignore[arg-type]
                "success": True,
                "cancelled": True,
                "paths": [],
                "documents": self.session.get_available_documents(),
                "file_run_mappings": self.session.get_file_run_mappings(),
            })
            return

        registered = [self.session.register_document(p) for p in paths]
        send_json_response(self, 200, {  # type: ignore[arg-type]
            "success": True,
            "cancelled": False,
            "paths": registered,
            "active_file": self.session.pdf_path,
            "documents": self.session.get_available_documents(),
            "file_run_mappings": self.session.get_file_run_mappings(),
        })

    def _handle_post_add_document(self, payload: Dict[str, Any]) -> None:
        """
        Registers one or more document paths with the session and discovery mappings.
        No files are uploaded or copied; only their filesystem paths are made known to the backend.
        """
        raw_paths: List[str] = []
        if payload.get("paths") and isinstance(payload["paths"], list):
            raw_paths.extend(str(p) for p in payload["paths"] if p)
        for key in ("file_path", "path", "filename", "document_path"):
            val = payload.get(key)
            if val and str(val) not in raw_paths:
                raw_paths.append(str(val))

        if not raw_paths:
            send_json_response(self, 400, {  # type: ignore[arg-type]
                "success": False,
                "error": "Missing 'file_path', 'path', or 'paths' in request payload.",
            })
            return

        registered = [self.session.register_document(p) for p in raw_paths]
        send_json_response(self, 200, {  # type: ignore[arg-type]
            "success": True,
            "paths": registered,
            "file_path": registered[0] if registered else "",
            "active_file": self.session.pdf_path,
            "documents": self.session.get_available_documents(),
            "file_run_mappings": self.session.get_file_run_mappings(),
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
