"""
src/pipeline/server/routes/execution.py

Pipeline execution and rerun API route handlers for cernodata HTTP server.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from src.pipeline.planner_models import DocumentPlan, PlannerCriteria
from src.pipeline.server.http_utils import send_json_response
from src.pipeline.server.routes.base import BaseApiRoutesMixin, logger

if TYPE_CHECKING:
    from src.pipeline.execution_models import PipelineExecutionResult


class ExecutionRoutesMixin(BaseApiRoutesMixin):
    """Mixin handling live document pipeline execution and rerun endpoints."""

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
        if not force and not with_plan:
            cached = self.session.get_cached_preset_result(pdf_path, preset, language)
            if cached is not None:
                logger.info(
                    "Reusing existing result for preset '%s' (PDF: %s, Lang: %s)",
                    preset, pdf_path, language,
                )
                self.session.update_result_state(cached, pdf_path=pdf_path, language=language)
                dec = cached.get("decision", {})
                score = float(dec.get("overall_confidence", 1.0) or 1.0)
                status = str(dec.get("status", "ACCEPT"))
                self.session.set_completed(
                    status=status,
                    confidence=score,
                    violations_count=len(cached.get("violations", [])),
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
            criteria = PlannerCriteria(
                taxonomy=plan_config.get("taxonomy", "standard"),
                target=plan_config.get("target_use_case", "rag_vector_search"),
                security=plan_config.get("security", "air_gapped_local"),
            )
            plan_obj = planner.create_plan(
                document_path=pdf_path,
                criteria=criteria,
                language=language,
                target_threshold=threshold,
            )

        session = self.session
        on_progress = session.make_progress_callback()

        def _execute_run() -> PipelineExecutionResult:
            res = run_pipeline(
                pdf_path=pdf_path,
                target_threshold=threshold,
                language=language,
                preset=preset,
                align_skew=align_skew,
                visualize=visualize,
                plan=plan_obj,
                progress_callback=on_progress,
            )
            session.update_result_state(res, pdf_path=pdf_path, language=language)
            dec = res.get("decision", {})
            score = float(dec.get("overall_confidence", 1.0) or 1.0)
            status = str(dec.get("status", "ACCEPT"))
            t_end = datetime.now().strftime("%H:%M:%S")
            session.set_completed(
                status=status,
                confidence=score,
                violations_count=len(res.get("violations", [])),
                log=(
                    f"[{t_end}] [SUCCESS] Run complete: Status '{status}', "
                    f"Confidence: {score:.4f}, Violations: {len(res.get('violations', []))}."
                ),
            )
            return res

        try:
            future = self.executor.submit(_execute_run)
            result = future.result()
            send_json_response(self, 200, {  # type: ignore[arg-type]
                "success": True,
                "preset": preset,
                "language": language,
                "dom": result["dom"],
                "violations": result["violations"],
                "decision": result["decision"],
                "plan": result.get("plan"),
            })
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            logger.info("Client disconnected before pipeline result could be returned.")
        except Exception as e:
            t_err = datetime.now().strftime("%H:%M:%S")
            session.set_error(str(e), log=f"[{t_err}] [ERROR] Pipeline failure: {e}")
            send_json_response(self, 500, {"success": False, "error": str(e)})  # type: ignore[arg-type]

    def _handle_post_rerun(self, payload: Dict[str, Any]) -> None:
        """
        Executes live pipeline rerun with alternative preset or reuses existing result.

        Args:
            payload: JSON request body dictionary.
        """
        preset = payload.get("preset", "docling_deep")
        pdf_path, language = self._extract_document_and_language(payload)
        force = bool(payload.get("force", payload.get("force_rerun", False)))

        if not force:
            cached = self.session.get_cached_preset_result(pdf_path, preset, language)
            if cached is not None:
                logger.info(
                    "Reusing existing result for preset '%s' (PDF: %s, Lang: %s)",
                    preset, pdf_path, language,
                )
                self.session.update_result_state(cached, pdf_path=pdf_path, language=language)
                dec = cached.get("decision", {})
                score = float(dec.get("overall_confidence", 1.0) or 1.0)
                status = str(dec.get("status", "ACCEPT"))
                self.session.set_completed(
                    status=status,
                    confidence=score,
                    violations_count=len(cached.get("violations", [])),
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

        try:
            future = self.executor.submit(_execute_rerun)
            result = future.result()
            send_json_response(self, 200, {  # type: ignore[arg-type]
                "success": True,
                "preset": preset,
                "language": language,
                "dom": result["dom"],
                "violations": result["violations"],
                "decision": result["decision"],
            })
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            logger.info("Client disconnected before rerun result could be returned.")
        except Exception as e:
            send_json_response(self, 500, {"success": False, "error": str(e)})  # type: ignore[arg-type]
