"""
src/pipeline/server/routes/execution.py

Pipeline execution and rerun API route handlers for cernodata HTTP server.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from src.pipeline.planner.models import DocumentPlan, PlannerCriteria
from src.pipeline.server.http_utils import send_json_response
from src.pipeline.server.routes.base import BaseApiRoutesMixin, logger

if TYPE_CHECKING:
    from src.pipeline.execution_models import PipelineExecutionResult


class ExecutionRoutesMixin(BaseApiRoutesMixin):
    """Mixin handling live document pipeline execution and rerun endpoints."""

    def _run_visual_test_suite_check(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """No-op hook for evaluating expectations and Q&A questions configured in the Web Hub UI."""
        # TODO(TASK-107): Evaluate expected section headers, table checks, and plain-English retrieval
        # questions submitted from the Web Hub 'Define Output Expectations & Test Questions' UI card.
        _ = payload
        return []

    def _run_fast_layout_preview(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """No-op hook for instant bounding-box layout preview in the Web Hub and Viewer UI."""
        # TODO(TASK-1002): Execute fast structure-only bounding-box extraction when the user clicks
        # 'Instant Layout Preview (Skip OCR)' in the Web Hub or Viewer toolbar.
        _ = payload
        return None

    def _try_serve_cached_preset(self, pdf_path: str, preset: str, language: str) -> bool:
        """Checks session preset cache and sends a 200 JSON response if a cached result exists."""
        cached = self.session.get_cached_preset_result(pdf_path, preset, language)
        if cached is None:
            return False
        logger.info("Reusing existing result for preset '%s' (PDF: %s, Lang: %s)", preset, pdf_path, language)
        self.session.update_result_state(cached, pdf_path=pdf_path, language=language)
        dec = cached.get("decision", {})
        raw_score = dec.get("overall_confidence")
        score = float(raw_score) if raw_score is not None else 0.0
        raw_status = dec.get("status")
        status = str(raw_status) if raw_status is not None else "UNKNOWN"
        viols = cached.get("violations", [])
        self.session.set_completed(
            status=status,
            confidence=score,
            violations_count=len(viols),
            log=f"[CACHE] Reused previous result for preset '{preset}' (Status: {status}, Confidence: {score:.4f}).",
        )
        send_json_response(self, 200, {  # type: ignore[arg-type]
            "success": True,
            "preset": preset,
            "language": language,
            "dom": cached["dom"],
            "violations": cached["violations"],
            "decision": cached["decision"],
            "plan": cached.get("plan"),
            "cached": True,
        })
        return True

    def _submit_and_send_run_result(
        self,
        task_fn: Callable[[], PipelineExecutionResult],
        preset: str,
        language: str,
        include_plan: bool = True,
        record_session_error: bool = False,
    ) -> None:
        """Submits an execution callable to the thread pool and sends the formatted HTTP response."""
        try:
            result = self.executor.submit(task_fn).result()
            response_body: Dict[str, Any] = {
                "success": True,
                "preset": preset,
                "language": language,
                "dom": result["dom"],
                "violations": result["violations"],
                "decision": result["decision"],
            }
            if include_plan:
                response_body["plan"] = result.get("plan")
            send_json_response(self, 200, response_body)  # type: ignore[arg-type]
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            logger.info("Client disconnected before pipeline result could be returned.")
        except Exception as e:
            if record_session_error:
                t_err = datetime.now().strftime("%H:%M:%S")
                self.session.set_error(str(e), log=f"[{t_err}] [ERROR] Pipeline failure: {e}")
            send_json_response(self, 500, {"success": False, "error": str(e)})  # type: ignore[arg-type]

    def _handle_post_run(self, payload: Dict[str, Any]) -> None:
        """
        Executes full document pipeline run asynchronously in server executor.

        Args:
            payload: JSON request body dictionary.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        pdf_path, language = self._extract_document_and_language(payload)
        threshold = float(payload.get("target_threshold", 0.85))
        preset = payload.get("preset", "docling_fast")
        align_skew = bool(payload.get("align_skew", True))
        visualize = bool(payload.get("visualize", True))
        with_plan = bool(payload.get("with_plan", False))
        plan_config = payload.get("plan_config")

        force = bool(payload.get("force", payload.get("force_rerun", False)))
        if not force and not with_plan and self._try_serve_cached_preset(pdf_path, preset, language):
            return

        self.session.reset_progress(
            initial_step="Step 1: Document Validation & Subdivision",
            log=f"[{timestamp}] [START] Ingestion initiated for '{pdf_path}' (Preset: {preset}, Lang: {language}).",
        )
        self.session.add_log(f"[{timestamp}] [STEP 1] Validating document structure and parameters...")

        from src.pipeline.orchestrator import run_pipeline
        from src.pipeline.planner import PresetPlanner

        plan_obj: Optional[DocumentPlan] = None
        if with_plan and plan_config:
            planner = PresetPlanner()
            raw_tax = str(plan_config.get("taxonomy", "standard"))
            tax_map = {
                "standard": "general_text",
                "scanned_archive": "scanned_form",
                "form_heavy": "financial_report",
                "multi_column_dense": "multicolumn_article",
            }
            resolved_tax = tax_map.get(raw_tax, raw_tax)

            raw_target = str(plan_config.get("target_use_case", "rag_vector_search"))
            lat = str(plan_config.get("latency", "balanced"))
            if lat == "maximum_accuracy" or raw_target in ("audit_compliance", "slm_fine_tuning"):
                resolved_target = "high_precision_structure"
            else:
                resolved_target = "rapid_approximate"

            criteria = PlannerCriteria(
                taxonomy=resolved_tax,
                target=resolved_target,
                security=plan_config.get("security", "air_gapped_local"),
            )

            primary_override = plan_config.get("primary_preset")
            fallback_override = plan_config.get("fallback_preset")
            override_order: Optional[List[str]] = None
            if primary_override and fallback_override:
                all_known = ["docling_fast", "docling_deep", "pypdfium_rapidocr", "vision_llm_direct"]
                rest = [p for p in all_known if p not in (primary_override, fallback_override)]
                override_order = [str(primary_override), str(fallback_override)] + rest
            elif primary_override:
                override_order = [str(primary_override)]

            raw_verif_layers = plan_config.get("verification_layers") or payload.get("verification_layers")
            resolved_verif_layers = [str(x) for x in raw_verif_layers] if isinstance(raw_verif_layers, (list, tuple)) else None

            plan_obj = planner.create_plan(
                document_path=pdf_path,
                criteria=criteria,
                language=language,
                target_threshold=threshold,
                override_order=override_order,
                verification_layers=resolved_verif_layers,
            )
            if plan_obj and plan_obj.primary_preset:
                preset = plan_obj.primary_preset
        elif not with_plan and self.session.submitted_plan:
            plan_obj = self.session.submitted_plan
            if plan_obj and plan_obj.primary_preset:
                preset = plan_obj.primary_preset

        session = self.session
        on_progress = session.make_progress_callback()
        direct_verif_layers = payload.get("verification_layers")
        resolved_run_layers = (
            [str(x) for x in direct_verif_layers]
            if isinstance(direct_verif_layers, (list, tuple))
            else None
        )

        def _execute_run() -> PipelineExecutionResult:
            res = run_pipeline(
                pdf_path=pdf_path,
                target_threshold=threshold,
                language=language,
                preset=preset,
                align_skew=align_skew,
                visualize=visualize,
                plan=plan_obj,
                verification_layers=resolved_run_layers,
                progress_callback=on_progress,
            )
            session.update_result_state(res, pdf_path=pdf_path, language=language)
            dec = res.get("decision", {})
            raw_score = dec.get("overall_confidence")
            score = float(raw_score) if raw_score is not None else 0.0

            raw_status = dec.get("status")
            status = str(raw_status) if raw_status is not None else "UNKNOWN"

            viols = res.get("violations", [])
            viols_count = len(viols)

            t_end = datetime.now().strftime("%H:%M:%S")
            from src.pipeline.server.run_mappings import record_run_mapping

            record_run_mapping(
                document_path=pdf_path,
                run_id=session.output_dir or "output",
                output_dir=session.output_dir or "output",
                preset=preset,
                status=status,
                confidence=score,
                violations_count=viols_count,
                total_pages=res.get("dom", {}).get("total_pages", 1) or 1,
                per_page_confidence=dec.get("per_page_confidence", {}),
                timestamp=t_end,
                repo_root=session.repo_root,
            )

            session.set_completed(
                status=status,
                confidence=score,
                violations_count=viols_count,
                log=(
                    f"[{t_end}] [SUCCESS] Run complete: Status '{status}', "
                    f"Confidence: {score:.4f}, Violations: {viols_count}."
                ),
            )
            return res

        self._submit_and_send_run_result(
            task_fn=_execute_run,
            preset=preset,
            language=language,
            include_plan=True,
            record_session_error=True,
        )

    def _handle_post_rerun(self, payload: Dict[str, Any]) -> None:
        """
        Executes live pipeline rerun with alternative preset or reuses existing result.

        Args:
            payload: JSON request body dictionary.
        """
        preset = payload.get("preset", "docling_deep")
        pdf_path, language = self._extract_document_and_language(payload)
        force = bool(payload.get("force", payload.get("force_rerun", False)))

        if not force and self._try_serve_cached_preset(pdf_path, preset, language):
            return

        print(f"\n[SERVER API] Triggering live pipeline rerun for preset: '{preset}' (PDF: {pdf_path}, Lang: {language})...")
        from src.pipeline.orchestrator import run_pipeline

        session = self.session
        on_progress = session.make_progress_callback()

        def _execute_rerun() -> PipelineExecutionResult:
            res = run_pipeline(
                pdf_path=pdf_path,
                preset=preset,
                language=language,
                progress_callback=on_progress,
            )
            session.update_result_state(res, pdf_path=pdf_path, language=language)
            return res

        self._submit_and_send_run_result(
            task_fn=_execute_rerun,
            preset=preset,
            language=language,
            include_plan=False,
            record_session_error=False,
        )

    def _handle_post_remove_run(self, payload: Dict[str, Any]) -> None:
        """
        Removes a recorded pipeline parsing run from disk and persistent mappings.

        Args:
            payload: JSON request body containing run_id and optional output_dir / document_path.
        """
        run_id = str(payload.get("run_id", "")).strip()
        output_dir = payload.get("output_dir")
        document_path = payload.get("document_path")
        if not run_id and not output_dir:
            send_json_response(self, 400, {"success": False, "error": "Missing run_id or output_dir"})  # type: ignore[arg-type]
            return

        from src.pipeline.server.run_mappings import remove_run_mapping
        success = remove_run_mapping(
            run_id=run_id,
            output_dir=output_dir,
            document_path=document_path,
            repo_root=self.session.repo_root,
        )
        send_json_response(self, 200, {"success": success, "run_id": run_id})  # type: ignore[arg-type]
