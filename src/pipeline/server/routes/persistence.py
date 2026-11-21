"""
src/pipeline/server/routes/persistence.py

DOM, diff, and quality violation JSON persistence API route handlers for cernodata HTTP server.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from pydantic import ValidationError

from src.pipeline.server.http_utils import parse_run_dir_and_step
from src.pipeline.server.router import api_router
from src.pipeline.server.routes.base import BaseApiRoutesMixin, logger
from src.schemas.requests import SaveDomRequest, VerifyLayersRequest
from src.utils import mkdirs, safe_load_json, save_json


class PersistenceRoutesMixin(BaseApiRoutesMixin):
    """Mixin handling DocumentDOM, diff, and decision tree disk persistence."""

    def _handle_visual_downstream_connector(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """No-op hook for the Web Hub 'Connect Output to Pre-Existing Setup' visual wizard."""
        # TODO(TASK-301): Persist and test the user's watched local folder or local app webhook URL
        # configured in the Web Hub UI, and auto-forward formatted outputs via deliver_to_sink (TASK-304).
        _ = payload
        return {"connected": False}

    def _handle_export_reproducible_package(self, output_dir: str) -> Optional[str]:
        """No-op hook for the Web Hub 'Download Reproducible Pipeline' one-click export button."""
        # TODO(TASK-1001): Generate and return a self-contained, audit-friendly Python pipeline script
        # with all active UI settings baked in when the user clicks 'Download Reproducible Pipeline'.
        _ = output_dir
        return None

    def _handle_post_save_dom(self, payload: Dict[str, Any]) -> None:
        """
        Persists updated DocumentDOM JSON to output directory.

        Args:
            payload: Dictionary containing dom structure and target output_dir.
        """
        try:
            req = SaveDomRequest.model_validate(payload)
        except ValidationError as exc:
            self.send_bad_request(str(exc))
            return

        dom_data = req.dom
        raw_out = req.output_dir or self.session.output_dir or "output"
        output_dir, _ = parse_run_dir_and_step(raw_out)
        output_dir = output_dir or "output"

        mkdirs(output_dir)
        dom_file = save_json(os.path.join(output_dir, "document_dom.json"), dom_data)
        diff_data = req.diff
        violations_data = req.violations
        decision_data = req.decision
        for filename, item in (
            ("raw_document_dom.json", req.raw_dom),
            ("run_diff.json", diff_data),
            ("quality_violations.json", violations_data),
            ("decision_tree.json", decision_data),
        ):
            if item is not None:
                save_json(os.path.join(output_dir, filename), item)

        with self.session._lock:
            self.session.viewer_data = None
            if self.session.current_result:
                self.session.current_result["dom"] = dom_data
                if req.raw_dom is not None:
                    self.session.current_result["raw_dom"] = req.raw_dom
                if diff_data is not None:
                    self.session.current_result["diff"] = diff_data
                if violations_data is not None:
                    self.session.current_result["violations"] = violations_data
                if decision_data:
                    self.session.current_result["decision"] = decision_data
            if decision_data is not None and "attempts" in decision_data:
                self.session.preset_attempts = list(decision_data["attempts"])

            # Keep server-side preset cache synchronized with saved DOM
            if self.session.current_result:
                pdf_path = self.session.pdf_path or str(dom_data.get("source_filename") or "")
                curr_dec = self.session.current_result.get("decision")
                chosen_preset = str(
                    ((decision_data.get("chosen_preset") or decision_data.get("preset_id") or "") if decision_data else "")
                    or (
                        (curr_dec.get("chosen_preset") or curr_dec.get("preset_id") or "")
                        if isinstance(curr_dec, dict)
                        else ""
                    )
                )
                if chosen_preset:
                    self.session._preset_cache.put(
                        pdf_path=pdf_path,
                        preset=chosen_preset,
                        result=self.session.current_result,
                        language=self.session.language,
                    )

        # Update interactive_viewer.html on disk if it exists in the output directory
        html_candidates = [os.path.join(output_dir, "interactive_viewer.html")]
        if self.session.repo_root:
            html_candidates.append(os.path.join(self.session.repo_root, output_dir, "interactive_viewer.html"))
        for h_path in html_candidates:
            if os.path.exists(h_path):
                try:
                    with open(h_path, "r", encoding="utf-8") as f:
                        h_content = f.read()
                    import re
                    dom_str = json.dumps(dom_data)
                    new_h = re.sub(
                        r"(window\.VIEWER_DATA\s*=\s*\{[\s\S]*?dom:\s*)(?:\{[\s\S]*?\}|null)(\s*,\s*(?:raw_dom|violations):)",
                        lambda m: f"{m.group(1)}{dom_str}{m.group(2)}",
                        h_content,
                        count=1,
                    )
                    if new_h != h_content:
                        with open(h_path, "w", encoding="utf-8") as f:
                            f.write(new_h)
                except Exception as exc:
                    logger.warning("Could not update interactive_viewer.html at %s: %s", h_path, exc)

        nodes_len = len(dom_data.get("nodes", []))
        logger.info("Saved updated DocumentDOM to '%s' (%d nodes).", dom_file, nodes_len)
        self.send_ok({"path": dom_file})

    @api_router.post("/api/verify_layers", "/api/reverify", "/api/verify")
    def _handle_post_verify_layers(self, payload: Dict[str, Any]) -> None:
        """
        Re-evaluates document verification after finishing a run based on selected criteria
        and materializes the updated scores and violations into run artifacts and server session.

        Args:
            payload: Dictionary containing output_dir, verification_layers, language, and target_threshold.
        """
        try:
            req = VerifyLayersRequest.model_validate(payload)
        except ValidationError as exc:
            self.send_bad_request(str(exc))
            return

        target_dir, _ = parse_run_dir_and_step(req.output_dir or self.session.output_dir or "output")
        selected_layers = req.verification_layers
        language = req.language or self.session.language or "en"
        target_threshold = req.target_threshold

        from src.pipeline.orchestrator import PipelineOrchestrator
        try:
            orchestrator = PipelineOrchestrator()
            result = orchestrator.reverify(
                output_dir=target_dir,
                selected_layers=selected_layers,
                language=language,
                target_threshold=target_threshold,
            )
            with self.session._lock:
                self.session.viewer_data = None
                if self.session.current_result:
                    self.session.current_result["violations"] = result.violations
                    updated_dom = safe_load_json(os.path.join(target_dir, "document_dom.json"))
                    if isinstance(updated_dom, dict) and updated_dom:
                        self.session.current_result["dom"] = updated_dom
                    dec = self.session.current_result.get("decision")
                    if isinstance(dec, dict):
                        dec["overall_confidence"] = result.overall_confidence
                        dec["per_page_confidence"] = result.per_page_confidence
                        dec["selected_layers"] = result.selected_layers
                        dec["layer_scores"] = result.layer_scores
                        dec["status"] = result.status
                        dec["is_accepted"] = result.is_accepted
                        chosen_p = str(dec.get("chosen_preset") or dec.get("preset_id") or "")
                        if chosen_p:
                            self.session._preset_cache.put(
                                pdf_path=self.session.pdf_path or result.source_filename,
                                preset=chosen_p,
                                result=self.session.current_result,
                                language=language,
                            )

            self.send_ok({"result": result.to_dict()})
        except Exception as e:
            logger.exception("Layer re-verification failed for '%s'", target_dir)
            self.send_server_error(str(e))

