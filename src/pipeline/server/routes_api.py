"""
src/pipeline/server/routes_api.py

API endpoint actions, pipeline run execution, DOM persistence,
and OCR parsing handlers for the cernodata HTTP server.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from src.parsers.section_ocr import parse_image_ocr, parse_section_from_pdf
from src.pipeline.planner_models import DocumentPlan, PlannerCriteria
from src.pipeline.planner_options import (
    DEFAULT_PRESET_WEIGHTS,
    SECURITY_OPTIONS,
    TARGET_OPTIONS,
    TAXONOMY_OPTIONS,
    WIZARD_DIMENSIONS,
)
from src.pipeline.server.http_utils import parse_run_dir_and_step, send_json_response
from src.utils import mkdirs, resolve_pdf_path

if TYPE_CHECKING:
    from src.pipeline.execution_models import PipelineExecutionResult
    from src.pipeline.server.session import ServerSessionContext

logger = logging.getLogger("cernodata.server.routes_api")


class ApiRoutesMixin:
    """
    Mixin providing REST API route handlers for pipeline triggering,
    asynchronous execution, plan persistence, and OCR parsing.
    """

    server: Any

    @property
    def session(self) -> ServerSessionContext:
        """Session context provided by host request handler."""
        raise NotImplementedError

    @property
    def executor(self) -> ThreadPoolExecutor:
        """Worker thread pool executor provided by host request handler."""
        raise NotImplementedError

    def _extract_document_and_language(self, payload: Dict[str, Any]) -> Tuple[str, str]:
        """
        Extracts and resolves document path and language from request payload or session state.

        Args:
            payload: JSON request body dictionary.

        Returns:
            Tuple of (resolved_document_path, language_code).
        """
        raw_pdf = payload.get("pdf_path") or self.session.pdf_path or "src/e2e/Document 8.pdf"
        pdf_path = resolve_pdf_path(raw_pdf)
        language = payload.get("language") or self.session.language or "en"
        return pdf_path, language

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
        default_doc = getattr(self.server, "default_doc", None) or self.session.pdf_path or "src/e2e/Document 8.pdf"
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

    def _handle_post_calculate_scores(self, payload: Dict[str, Any]) -> None:
        """
        Calculates preset scores based on data shape questionnaire criteria.

        Args:
            payload: Questionnaire criteria dictionary.
        """
        from src.pipeline.planner import PresetPlanner
        planner = getattr(self.server, "planner", None) or PresetPlanner()
        criteria = PlannerCriteria.from_dict(payload)
        scores = planner.calculate_scores(criteria=criteria)
        suggested = planner.suggest_preset_order(scores)

        send_json_response(self, 200, {  # type: ignore[arg-type]
            "success": True,
            "scores": scores,
            "suggested_order": suggested,
        })

    def _handle_post_submit_plan(self, payload: Dict[str, Any]) -> None:
        """
        Configures, validates, and persists a DocumentPlan.

        Args:
            payload: Plan parameters or serialized plan dictionary.
        """
        from src.pipeline.planner import PresetPlanner
        planner = getattr(self.server, "planner", None) or PresetPlanner()

        if "primary_preset" in payload or ("target_threshold" in payload and "steps" in payload):
            plan = DocumentPlan.from_dict(payload)
        else:
            default_doc = getattr(self.server, "default_doc", None) or self.session.pdf_path
            raw_doc = payload.get("document_path")
            document_path = raw_doc.strip() if isinstance(raw_doc, str) else ""
            document_path = document_path or default_doc or ""
            criteria = PlannerCriteria.from_dict(payload)
            raw_lang = payload.get("language")
            language = (
                raw_lang.strip()
                if (isinstance(raw_lang, str) and raw_lang.strip() and raw_lang.strip().lower() != "none")
                else None
            )
            try:
                default_thresh = getattr(self.server, "default_threshold", 0.82)
                target_threshold = float(payload.get("target_threshold", default_thresh))
            except (ValueError, TypeError):
                target_threshold = getattr(self.server, "default_threshold", 0.82)

            override_primary = payload.get("override_primary")
            override_order = payload.get("override_order")

            plan = planner.create_plan(
                document_path=document_path,
                criteria=criteria,
                language=language,
                target_threshold=target_threshold,
                override_primary=override_primary,
                override_order=override_order,
            )

        self.session.submitted_plan = plan
        setattr(self.server, "submitted_plan", plan)

        out_dir = getattr(self.server, "output_dir", None) or "output"
        if out_dir:
            mkdirs(out_dir)
            plan_file = os.path.join(out_dir, "plan.json")
            plan.save(plan_file)
        else:
            plan_file = ""

        resp_data: Dict[str, Any] = {
            "success": True,
            "plan_path": plan_file,
            "plan": plan.to_dict(),
            "message": (
                "Plan successfully configured and saved."
                if plan_file
                else "Plan successfully configured but not saved (no output directory)."
            ),
        }
        send_json_response(self, 200, resp_data)  # type: ignore[arg-type]

        if getattr(self.server, "shutdown_on_submit", False):
            threading.Thread(target=self.server.shutdown, daemon=True).start()

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
            self.session.current_result.update({"dom": dom_data, "diff": diff_data or {}, "violations": violations_data or []})
            if decision_data:
                self.session.current_result["decision"] = decision_data
        if isinstance(decision_data, dict) and "attempts" in decision_data:
            self.session.preset_attempts = list(decision_data["attempts"])

        nodes_len = len(dom_data.get("nodes", [])) if isinstance(dom_data, dict) else 0
        print(f"\n[SERVER API] Saved updated DocumentDOM to '{dom_file}' ({nodes_len} nodes).")
        send_json_response(self, 200, {"success": True, "path": dom_file})  # type: ignore[arg-type]

    def _handle_post_parse_ocr(self, payload: Dict[str, Any]) -> None:
        """
        Parses selected DOM section or image via OCR.

        Args:
            payload: Dictionary with image_base64 or (pdf_path and bbox), node_id, page, language.
        """
        node_id = payload.get("node_id", "")
        image_base64 = payload.get("image_base64")
        bbox = payload.get("bbox")
        try:
            page = int(payload.get("page") or 1)
        except (ValueError, TypeError):
            page = 1
        pdf_path = payload.get("pdf_path") or self.session.pdf_path
        language = payload.get("language") or self.session.language or "en"

        print(f"\n[SERVER API] Parsing selected section '{node_id}' using OCR (Lang: {language})...")

        ocr_result: Any
        if image_base64:
            ocr_result = parse_image_ocr(image_base64, language=language)
        elif pdf_path and bbox:
            ocr_result = parse_section_from_pdf(pdf_path, page, bbox, language=language)
        else:
            send_json_response(self, 400, {  # type: ignore[arg-type]
                "success": False,
                "error": "Either image_base64 or (pdf_path and bbox) must be provided.",
            })
            return

        if not isinstance(ocr_result, dict):
            ocr_result = {"success": False, "error": "Invalid OCR result structure"}

        response_data = {
            "success": ocr_result.get("success", False),
            "node_id": node_id,
            "text": ocr_result.get("text", ""),
            "confidence": ocr_result.get("confidence", 0.0),
            "lines": ocr_result.get("lines", []),
            "error": ocr_result.get("error"),
        }
        send_json_response(self, 200 if response_data["success"] else 422, response_data)  # type: ignore[arg-type]
