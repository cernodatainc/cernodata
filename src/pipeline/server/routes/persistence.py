"""
src/pipeline/server/routes/persistence.py

DOM, diff, and quality violation JSON persistence API route handlers for cernodata HTTP server.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from src.pipeline.server.http_utils import parse_run_dir_and_step, send_json_response
from src.pipeline.server.router import api_router
from src.pipeline.server.routes.base import BaseApiRoutesMixin, logger
from src.utils import mkdirs


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
        dom_data = payload.get("dom")
        output_dir, _ = parse_run_dir_and_step(payload.get("output_dir", "output"))

        if not dom_data:
            send_json_response(self, 400, {"error": "Missing dom payload"})  # type: ignore[arg-type]
            return

        mkdirs(output_dir)
        dom_file = os.path.join(output_dir, "document_dom.json")
        with open(dom_file, "w", encoding="utf-8") as f:
            json.dump(dom_data, f, indent=2)

        raw_dom = payload.get("raw_dom")
        if raw_dom is not None:
            raw_file = os.path.join(output_dir, "raw_document_dom.json")
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(raw_dom, f, indent=2)

        diff_data = payload.get("diff")
        if diff_data is not None:
            diff_file = os.path.join(output_dir, "run_diff.json")
            with open(diff_file, "w", encoding="utf-8") as f:
                json.dump(diff_data, f, indent=2)

        violations_data = payload.get("violations")
        if violations_data is not None:
            viol_file = os.path.join(output_dir, "quality_violations.json")
            with open(viol_file, "w", encoding="utf-8") as f:
                json.dump(violations_data, f, indent=2)

        decision_data = payload.get("decision")
        if decision_data is not None:
            dec_file = os.path.join(output_dir, "decision_tree.json")
            with open(dec_file, "w", encoding="utf-8") as f:
                json.dump(decision_data, f, indent=2)

        self.session.viewer_data = None
        if self.session.current_result:
            result_diff = diff_data or {}
            result_violations = violations_data or []
            self.session.current_result.update({
                "dom": dom_data,
                "diff": result_diff,
                "violations": result_violations,
            })
            if decision_data:
                self.session.current_result["decision"] = decision_data
        if isinstance(decision_data, dict) and "attempts" in decision_data:
            self.session.preset_attempts = list(decision_data["attempts"])

        # Keep server-side preset cache synchronized with saved DOM
        if self.session.current_result:
            pdf_path = self.session.pdf_path or dom_data.get("source_filename") or ""
            chosen_preset = (
                (decision_data.get("chosen_preset") if isinstance(decision_data, dict) else None)
                or (self.session.current_result.get("decision", {}).get("chosen_preset") if isinstance(self.session.current_result.get("decision"), dict) else None)
                or "docling_fast"
            )
            self.session._preset_cache.put(
                pdf_path=pdf_path,
                preset=chosen_preset,
                result=self.session.current_result,
                language=self.session.language,
            )

        # Update interactive_viewer.html on disk if it exists in the output directory
        html_candidates = [os.path.join(output_dir, "interactive_viewer.html")]
        if hasattr(self.session, "repo_root") and self.session.repo_root:
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

        nodes_len = len(dom_data.get("nodes", [])) if isinstance(dom_data, dict) else 0
        logger.info("Saved updated DocumentDOM to '%s' (%d nodes).", dom_file, nodes_len)
        send_json_response(self, 200, {"success": True, "path": dom_file})  # type: ignore[arg-type]

    @api_router.post("/api/verify_layers", "/api/reverify", "/api/verify")
    def _handle_post_verify_layers(self, payload: Dict[str, Any]) -> None:
        """
        Re-evaluates document verification after finishing a run based on selected criteria
        and materializes the updated scores and violations into run artifacts and server session.

        Args:
            payload: Dictionary containing output_dir, verification_layers, language, and target_threshold.
        """
        raw_out = payload.get("output_dir")
        target_dir, _ = parse_run_dir_and_step(raw_out or self.session.output_dir or "output")
        raw_layers = payload.get("verification_layers")
        selected_layers = [str(x) for x in raw_layers] if isinstance(raw_layers, (list, tuple)) else None
        language = payload.get("language") or self.session.language or "en"
        try:
            target_threshold = float(payload.get("target_threshold", 0.82))
        except (ValueError, TypeError):
            target_threshold = 0.82

        from src.pipeline.orchestrator import PipelineOrchestrator
        try:
            orchestrator = PipelineOrchestrator()
            result = orchestrator.reverify(
                output_dir=target_dir,
                selected_layers=selected_layers,
                language=language,
                target_threshold=target_threshold,
            )
            self.session.viewer_data = None
            if self.session.current_result:
                self.session.current_result["violations"] = result.violations
                if "decision" in self.session.current_result:
                    dec = self.session.current_result["decision"]
                    dec["overall_confidence"] = result.overall_confidence
                    dec["per_page_confidence"] = result.per_page_confidence
                    dec["selected_layers"] = result.selected_layers
                    dec["layer_scores"] = result.layer_scores
                    dec["status"] = result.status

            send_json_response(self, 200, {  # type: ignore[arg-type]
                "success": True,
                "result": result.to_dict(),
            })
        except Exception as e:
            logger.exception("Layer re-verification failed for '%s'", target_dir)
            send_json_response(self, 500, {  # type: ignore[arg-type]
                "success": False,
                "error": str(e),
            })

