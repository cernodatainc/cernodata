"""
src/pipeline/server/routes/config.py

Configuration and run retrieval API endpoints for cernodata HTTP server.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from src.pipeline.parsers.registry import get_default_parser_registry
from src.pipeline.planner import PresetPlanner
from src.pipeline.planner.options import (
    DEFAULT_PRESET_WEIGHTS,
    SECURITY_OPTIONS,
    TARGET_OPTIONS,
    TAXONOMY_OPTIONS,
    WIZARD_DIMENSIONS,
)
from src.quality.layers import ALL_VERIFICATION_LAYERS, DEFAULT_VERIFICATION_LAYERS, LAYER_METADATA
from src.pipeline.server.routes.base import BaseApiRoutesMixin, logger
from src.schemas.custom_preset import (
    CustomPresetConfig,
    PresetBackendType,
    get_community_preset_recipes,
    load_custom_presets_file,
    save_custom_presets_file,
)


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
            self.send_bad_request("Missing output_dir parameter")
            return
        loaded = self.session.load_previous_run(target_dir)
        self.send_ok({
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
            self.send_ok({
                "cancelled": True,
                "paths": [],
                "documents": self.session.get_available_documents(),
                "file_run_mappings": self.session.get_file_run_mappings(),
            })
            return

        registered = [r for r in (self.session.register_document(p) for p in paths) if r]
        self.send_ok({
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
            self.send_bad_request("Missing 'file_path', 'path', or 'paths' in request payload.")
            return

        registered = [r for r in (self.session.register_document(p) for p in raw_paths) if r]
        self.send_ok({
            "paths": registered,
            "file_path": registered[0] if registered else "",
            "active_file": self.session.pdf_path,
            "documents": self.session.get_available_documents(),
            "file_run_mappings": self.session.get_file_run_mappings(),
        })

    def _handle_post_forget_file(self, payload: Dict[str, Any]) -> None:
        """
        Marks a document as forgotten, removing it from explorer listings
        without deleting historical execution runs or output artifacts.
        """
        raw_path = payload.get("file_path") or payload.get("document_path") or payload.get("path")
        if not raw_path:
            self.send_bad_request("Missing 'file_path' or 'document_path' in request payload.")
            return

        target_file = str(raw_path).strip()
        from src.pipeline.server.run_mappings import forget_document
        forget_document(target_file, repo_root=self.session.repo_root)
        if hasattr(self.session, "forget_document"):
            self.session.forget_document(target_file)

        self.send_ok({
            "forgotten_file": target_file,
            "active_file": self.session.pdf_path,
            "documents": self.session.get_available_documents(),
            "file_run_mappings": self.session.get_file_run_mappings(),
        })

    def _handle_post_unforget_file(self, payload: Dict[str, Any]) -> None:
        """
        Unforgets a document, restoring it to workspace explorer listings.
        """
        raw_path = payload.get("file_path") or payload.get("document_path") or payload.get("path")
        if not raw_path:
            self.send_bad_request("Missing 'file_path' or 'document_path' in request payload.")
            return

        target_file = str(raw_path).strip()
        from src.pipeline.server.run_mappings import unforget_document
        unforget_document(target_file, repo_root=self.session.repo_root)

        self.send_ok({
            "unforgotten_file": target_file,
            "active_file": self.session.pdf_path,
            "documents": self.session.get_available_documents(),
            "file_run_mappings": self.session.get_file_run_mappings(),
        })

    def _resolve_custom_presets_path(self) -> str:
        """Resolves the JSON manifest path for persisting user-defined custom presets."""
        configured = getattr(self.server, "custom_presets_path", None)
        if configured:
            return str(configured)
        srv_out = getattr(self.server, "output_dir", None)
        if srv_out:
            return os.path.join(str(srv_out), "custom_presets.json")
        return os.path.join("output", "custom_presets.json")

    def _get_custom_presets_catalog(self) -> List[Dict[str, Any]]:
        """Returns user-saved CustomPresetConfig entries and community OCR recipes for the Web Hub UI."""
        catalog: List[Dict[str, Any]] = []
        user_presets = load_custom_presets_file(self._resolve_custom_presets_path())
        user_ids = {cfg.preset_id for cfg in user_presets}

        for cfg in user_presets:
            entry = cfg.to_dict()
            entry["source"] = "user"
            entry["installed"] = True
            entry["suitability_weights"] = PresetPlanner.derive_custom_preset_weights(cfg)
            catalog.append(entry)

        for recipe in get_community_preset_recipes():
            entry = recipe.to_dict()
            entry["source"] = "community"
            entry["installed"] = recipe.preset_id in user_ids
            entry["suitability_weights"] = PresetPlanner.derive_custom_preset_weights(recipe)
            catalog.append(entry)

        return catalog

    def _handle_get_presets(self) -> None:
        """Returns user-registered presets, community recipes, and combined UI catalog."""
        user_presets = load_custom_presets_file(self._resolve_custom_presets_path())
        community = get_community_preset_recipes()
        self.send_ok({
            "presets": [p.to_dict() for p in user_presets],
            "community_recipes": [r.to_dict() for r in community],
            "catalog": self._get_custom_presets_catalog(),
        })

    def _handle_post_presets(self, payload: Dict[str, Any]) -> None:
        """Validates, persists, and registers a user-defined custom OCR preset."""
        try:
            config = CustomPresetConfig.from_dict(payload)
        except ValueError as exc:
            self.send_bad_request(str(exc))
            return

        path = self._resolve_custom_presets_path()
        existing = load_custom_presets_file(path)
        updated = [item for item in existing if item.preset_id != config.preset_id]
        updated.append(config)
        save_custom_presets_file(path, updated)

        get_default_parser_registry().register_custom_preset(config, prepend=True)

        active_planner = getattr(self.server, "planner", None)
        if active_planner is None:
            setattr(self.server, "planner", PresetPlanner(custom_presets=updated))
        else:
            active_planner.register_custom_preset(config)

        self.send_ok({
            "preset": config.to_dict(),
            "suitability_weights": PresetPlanner.derive_custom_preset_weights(config),
            "custom_presets": self._get_custom_presets_catalog(),
        })

    def _handle_post_test_preset(self, payload: Dict[str, Any]) -> None:
        """Verifies CLI executable presence or HTTP endpoint reachability for a custom preset draft."""
        probe_payload = dict(payload)
        probe_payload["preset_id"] = payload.get("preset_id") or "test_preset"
        probe_payload["display_name"] = payload.get("display_name") or "Test Preset"
        try:
            config = CustomPresetConfig.from_dict(probe_payload)
        except ValueError as exc:
            self.send_bad_request(str(exc))
            return

        if config.backend_type == PresetBackendType.CLI_SUBPROCESS:
            exe = config.command_template[0] if config.command_template else ""
            resolved = shutil.which(exe) or (exe if exe and os.path.isfile(exe) else None)
            if resolved:
                self.send_json(200, {
                    "success": True,
                    "reachable": True,
                    "backend_type": config.backend_type.value,
                    "executable": resolved,
                    "message": f"Executable found at '{resolved}'.",
                })
            else:
                self.send_json(200, {
                    "success": False,
                    "reachable": False,
                    "backend_type": config.backend_type.value,
                    "executable": None,
                    "error": f"Executable '{exe}' was not found on PATH.",
                })
            return

        if config.backend_type == PresetBackendType.HTTP_ENDPOINT:
            url = config.endpoint_url or ""
            timeout = min(int(config.timeout_sec), 5)
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    status_code = getattr(resp, "status", 200)
                self.send_json(200, {
                    "success": True,
                    "reachable": True,
                    "backend_type": config.backend_type.value,
                    "status_code": status_code,
                    "message": f"HTTP endpoint reachable (status {status_code}).",
                })
            except urllib.error.HTTPError as exc:
                logger.debug("Preset test probe received HTTP status %s for '%s'", exc.code, url)
                self.send_json(200, {
                    "success": True,
                    "reachable": True,
                    "backend_type": config.backend_type.value,
                    "status_code": exc.code,
                    "message": f"HTTP endpoint responded with status {exc.code}.",
                })
            except (urllib.error.URLError, OSError, ValueError) as exc:
                logger.info("Preset HTTP connectivity check failed for '%s': %s", url, exc)
                self.send_json(200, {
                    "success": False,
                    "reachable": False,
                    "backend_type": config.backend_type.value,
                    "error": str(exc),
                })
            return

        self.send_json(200, {
            "success": False,
            "reachable": False,
            "backend_type": config.backend_type.value,
            "error": f"Connection testing is not supported for backend '{config.backend_type.value}'.",
        })

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

        preset_weights: Dict[str, Dict[str, float]] = {
            k: dict(v) for k, v in DEFAULT_PRESET_WEIGHTS.items()
        }
        for cfg in load_custom_presets_file(self._resolve_custom_presets_path()):
            preset_weights[cfg.preset_id] = PresetPlanner.derive_custom_preset_weights(cfg)

        self.send_json(200, {
            "default_doc": default_doc,
            "default_lang": default_lang,
            "default_threshold": default_thresh,
            "preset_weights": preset_weights,
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
