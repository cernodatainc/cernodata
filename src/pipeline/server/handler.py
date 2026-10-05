"""
src/pipeline/server/handler.py

HTTP request handler serving landing page, viewer assets, hydration API, and execution endpoints.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import parse_qs, urlparse

from src.parsers.section_ocr import parse_image_ocr, parse_section_from_pdf
from src.pipeline.planner_models import DocumentPlan, PlannerCriteria
from src.pipeline.planner_options import (
    DEFAULT_PRESET_WEIGHTS,
    SECURITY_OPTIONS,
    TARGET_OPTIONS,
    TAXONOMY_OPTIONS,
    WIZARD_DIMENSIONS,
)
from src.pipeline.server.common import (
    REPO_ROOT,
    SRC_DIR,
    calculate_progress_step,
    read_json_payload,
    send_file_response,
    send_html_response,
    send_json_response,
    send_text_response,
)
from src.pipeline.server.session import ServerSessionContext
from src.utils import mkdirs, resolve_pdf_path

logger = logging.getLogger("cernodata.server.handler")


class PipelineViewerHandler(SimpleHTTPRequestHandler):
    """HTTP request handler serving landing page, viewer assets, hydration API, and execution endpoints."""

    def handle(self) -> None:
        """Handles request while catching normal client socket aborts."""
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
            logger.debug("Client disconnected during connection handling: %s", e)

    _default_session: ServerSessionContext = ServerSessionContext()
    _fallback_executor: Optional[ThreadPoolExecutor] = None

    pdf_path: str = ""
    language: str = "en"
    viewer_data: Optional[Dict[str, Any]] = None
    current_result: Optional[Dict[str, Any]] = None
    preset_attempts: List[Dict[str, Any]] = []
    progress_state: Dict[str, Any] = {
        "status": "idle",
        "progress": 0,
        "step_index": 0,
        "current_step": "Idle - ready to execute",
        "logs": ["[INIT] Server ready. Waiting to trigger pipeline."],
        "completed": False,
        "error": None,
    }

    @property
    def session(self) -> ServerSessionContext:
        """Returns the thread-safe session context attached to the server or default fallback."""
        if hasattr(self.server, "session_context") and self.server.session_context is not None:
            return self.server.session_context
        return self.__class__._default_session

    @property
    def executor(self) -> ThreadPoolExecutor:
        """Returns the thread pool executor attached to the server or creates a fallback."""
        if hasattr(self.server, "executor") and self.server.executor is not None:
            return self.server.executor
        if self.__class__._fallback_executor is None:
            self.__class__._fallback_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fallback-worker")
        return self.__class__._fallback_executor

    @classmethod
    def get_available_documents(cls) -> List[str]:
        """Finds candidate PDF documents in repository delegating to default session."""
        return cls._default_session.get_available_documents()

    @classmethod
    def get_previous_runs(cls) -> List[Dict[str, Any]]:
        """Returns discovered completed output directories delegating to default session."""
        return cls._default_session.get_previous_runs()

    @classmethod
    def load_previous_run(cls, output_dir: str) -> Dict[str, Any]:
        """Loads and switches default session to an existing output directory."""
        res = cls._default_session.load_previous_run(output_dir)
        cls.pdf_path = cls._default_session.pdf_path
        cls.language = cls._default_session.language
        cls.viewer_data = cls._default_session.viewer_data
        cls.current_result = cls._default_session.current_result
        cls.preset_attempts = cls._default_session.preset_attempts
        return res

    @classmethod
    def get_viewer_data(cls) -> Dict[str, Any]:
        """Returns structured data required to hydrate the interactive visual viewer."""
        return cls._default_session.get_viewer_data()

    @classmethod
    def update_result_state(cls, result: Mapping[str, Any], pdf_path: str, language: str) -> None:
        """Updates server memory state and hydration dataset from run_pipeline result."""
        cls._default_session.update_result_state(result, pdf_path, language)
        cls.pdf_path = cls._default_session.pdf_path
        cls.language = cls._default_session.language
        cls.viewer_data = cls._default_session.viewer_data
        cls.current_result = cls._default_session.current_result
        cls.preset_attempts = cls._default_session.preset_attempts

    # -------------------------------------------------------------------------
    # Route Handlers: Static / HTML Content
    # -------------------------------------------------------------------------

    def _serve_landing_page(self) -> None:
        """Serves the interactive landing page / dashboard."""
        html_override = getattr(self.server, "html_content", "")
        if html_override:
            send_html_response(self, html_override)
            return

        landing_path = os.path.join(SRC_DIR, "visualization", "landing.html")
        if send_file_response(self, landing_path, "text/html; charset=utf-8"):
            return
        self.send_error(500, "Landing page template not found")

    def _serve_viewer_html(self) -> None:
        """Serves the un-templated viewer HTML shell for client-side hydration."""
        for candidate in (
            os.path.join(SRC_DIR, "visualization", "viewer", "viewer.html"),
            os.path.join(SRC_DIR, "visualization", "viewer", "template.html"),
        ):
            if send_file_response(self, candidate, "text/html; charset=utf-8"):
                return
        self.send_error(500, "Viewer template not found")

    def _serve_interactive_viewer_compat(self) -> None:
        """Serves backwards-compatible interactive viewer HTML."""
        for candidate in (
            os.path.join(REPO_ROOT, self.session.output_dir or "output", "interactive_viewer.html"),
            os.path.join(REPO_ROOT, "output", "interactive_viewer.html"),
            os.path.join(SRC_DIR, "visualization", "viewer", "viewer.html"),
        ):
            if send_file_response(self, candidate, "text/html; charset=utf-8"):
                return
        self.send_error(404, "Interactive viewer not found")

    def _serve_planner_page(self) -> None:
        """Serves data shape questionnaire HTML page."""
        html_override = getattr(self.server, "html_content", "")
        if html_override:
            send_html_response(self, html_override)
            return

        candidate_paths = [
            os.path.join(REPO_ROOT, self.session.output_dir or "output", "data_shape_config.html"),
            os.path.join(REPO_ROOT, "output", "data_shape_config.html"),
            os.path.join(SRC_DIR, "visualization", "data_shape_config.html"),
        ]
        for target_file in candidate_paths:
            if send_file_response(self, target_file, "text/html; charset=utf-8"):
                return
        self.send_error(404, "Planner page not found")

    # -------------------------------------------------------------------------
    # Route Handlers: GET APIs
    # -------------------------------------------------------------------------

    def _handle_load_run(self, target_dir: str) -> None:
        """Executes run loading and sends standard response."""
        if not target_dir:
            send_json_response(self, 400, {"success": False, "error": "Missing output_dir parameter"})
            return
        loaded = self.session.load_previous_run(target_dir)
        send_json_response(self, 200, {
            "success": True,
            "output_dir": self.session.output_dir,
            "run": loaded,
            "results": self.session.get_results(),
        })

    def _handle_api_config(self) -> None:
        """Returns runtime server configuration and preset options."""
        default_doc = getattr(self.server, "default_doc", None) or self.session.pdf_path or "src/e2e/Document 8.pdf"
        default_lang = getattr(self.server, "default_lang", None) or self.session.language or "en"
        default_thresh = getattr(self.server, "default_threshold", 0.85)

        send_json_response(self, 200, {
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

    # -------------------------------------------------------------------------
    # Route Dispatchers: do_GET and do_POST
    # -------------------------------------------------------------------------

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        raw_path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        if raw_path in ("", "/", "/index.html", "/landing", "/hub"):
            self._serve_landing_page()
        elif raw_path in ("/viewer", "/viewer.html"):
            self._serve_viewer_html()
        elif raw_path == "/interactive_viewer.html":
            self._serve_interactive_viewer_compat()
        elif raw_path == "/viewer.css":
            css_path = os.path.join(SRC_DIR, "visualization", "viewer", "viewer.css")
            if not send_file_response(self, css_path, "text/css; charset=utf-8"):
                self.send_error(404, "CSS asset not found")
        elif raw_path == "/viewer.js":
            from src.visualization.viewer.scripts import get_viewer_js
            send_text_response(self, get_viewer_js(), content_type="application/javascript; charset=utf-8")
        elif raw_path in ("/landing.css", "landing.css"):
            css_path = os.path.join(SRC_DIR, "visualization", "landing.css")
            if not send_file_response(self, css_path, "text/css; charset=utf-8"):
                self.send_error(404, "Landing CSS asset not found")
        elif raw_path in ("/landing.js", "landing.js"):
            js_path = os.path.join(SRC_DIR, "visualization", "landing.js")
            if not send_file_response(self, js_path, "application/javascript; charset=utf-8"):
                self.send_error(404, "Landing JS asset not found")
        elif raw_path in ("/data_shape_config.css", "data_shape_config.css"):
            candidate_paths = [
                os.path.join(REPO_ROOT, self.session.output_dir or "output", "data_shape_config.css"),
                os.path.join(REPO_ROOT, "output", "data_shape_config.css"),
                os.path.join(SRC_DIR, "visualization", "data_shape_config.css"),
            ]
            for target_file in candidate_paths:
                if send_file_response(self, target_file, "text/css; charset=utf-8"):
                    break
            else:
                self.send_error(404, "Data shape config CSS asset not found")
        elif raw_path in ("/data_shape_config.js", "data_shape_config.js"):
            candidate_paths = [
                os.path.join(REPO_ROOT, self.session.output_dir or "output", "data_shape_config.js"),
                os.path.join(REPO_ROOT, "output", "data_shape_config.js"),
                os.path.join(SRC_DIR, "visualization", "data_shape_config.js"),
            ]
            for target_file in candidate_paths:
                if send_file_response(self, target_file, "application/javascript; charset=utf-8"):
                    break
            else:
                self.send_error(404, "Data shape config JS asset not found")
        elif raw_path in ("/data_shape_config.html", "/data_shape", "/planner"):
            self._serve_planner_page()
        elif raw_path == "/api/config":
            self._handle_api_config()
        elif raw_path in ("/api/previous_runs", "/api/runs"):
            send_json_response(self, 200, {
                "runs": self.session.get_previous_runs(),
                "active_run": self.session.output_dir,
            })
        elif raw_path == "/api/load_run":
            self._handle_load_run(query_params.get("output_dir", [""])[0])
        elif raw_path == "/api/documents":
            send_json_response(self, 200, {"documents": self.session.get_available_documents()})
        elif raw_path == "/api/progress":
            send_json_response(self, 200, self.session.get_progress())
        elif raw_path == "/api/results":
            res_target_dir: Optional[str] = query_params.get("output_dir", [""])[0] or None
            send_json_response(self, 200, self.session.get_results(output_dir=res_target_dir))
        elif raw_path == "/api/viewer_data":
            v_target_dir: Optional[str] = query_params.get("output_dir", [""])[0] or None
            send_json_response(self, 200, self.session.get_viewer_data(output_dir=v_target_dir))
        else:
            self.send_error(404, f"Endpoint not found: {raw_path}")

    def do_POST(self) -> None:
        payload = read_json_payload(self)

        if self.path == "/api/load_run":
            target_dir = payload.get("output_dir") or payload.get("run_id") or "output"
            self._handle_load_run(target_dir)
        elif self.path == "/api/run":
            self._handle_post_run(payload)
        elif self.path == "/api/rerun":
            self._handle_post_rerun(payload)
        elif self.path == "/api/calculate_scores":
            self._handle_post_calculate_scores(payload)
        elif self.path == "/api/submit_plan":
            self._handle_post_submit_plan(payload)
        elif self.path == "/api/save_dom":
            self._handle_post_save_dom(payload)
        elif self.path in ("/api/parse_section_ocr", "/api/ocr_section"):
            self._handle_post_parse_ocr(payload)
        else:
            self.send_error(404, "Endpoint not found")

    # -------------------------------------------------------------------------
    # Route Handlers: POST APIs
    # -------------------------------------------------------------------------

    def _handle_post_run(self, payload: Dict[str, Any]) -> None:
        """Executes full document pipeline run asynchronously in server executor."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        raw_pdf = payload.get("pdf_path", self.session.pdf_path) or "src/e2e/Document 8.pdf"
        pdf_path = resolve_pdf_path(raw_pdf)
        language = payload.get("language", self.session.language)
        threshold = float(payload.get("target_threshold", 0.85))
        preset = payload.get("preset", "docling_fast")
        align_skew = bool(payload.get("align_skew", True))
        visualize = bool(payload.get("visualize", True))
        with_plan = bool(payload.get("with_plan", False))
        plan_config = payload.get("plan_config")

        self.session.reset_progress(
            initial_step="Step 1: Document Validation & Subdivision",
            log=f"[{timestamp}] [START] Ingestion initiated for '{pdf_path}' (Preset: {preset}, Lang: {language}).",
        )
        self.session.add_log(f"[{timestamp}] [STEP 1] Validating document structure and parameters...")

        from src.pipeline.orchestrator import PipelineExecutionResult, run_pipeline
        from src.pipeline.planner import PresetPlanner

        plan_obj = None
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

        def on_progress(pct: int, step_desc: str, log_msg: str) -> None:
            t = datetime.now().strftime("%H:%M:%S")
            session.update_progress(
                progress=pct,
                step_index=calculate_progress_step(pct),
                current_step=step_desc,
                log=f"[{t}] {log_msg}",
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
                log=f"[{t_end}] [SUCCESS] Run complete: Status '{status}', Confidence: {score:.4f}, Violations: {len(res.get('violations', []))}.",
            )
            return res

        try:
            future = self.executor.submit(_execute_run)
            result = future.result()
            send_json_response(self, 200, {
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
            send_json_response(self, 500, {"success": False, "error": str(e)})

    def _handle_post_rerun(self, payload: Dict[str, Any]) -> None:
        """Executes live pipeline rerun with alternative preset."""
        preset = payload.get("preset", "docling_deep")
        raw_pdf = payload.get("pdf_path", self.session.pdf_path) or "src/e2e/Document 8.pdf"
        pdf_path = resolve_pdf_path(raw_pdf)
        language = payload.get("language", self.session.language)

        print(f"\n[SERVER API] Triggering live pipeline rerun for preset: '{preset}' (PDF: {pdf_path}, Lang: {language})...")
        from src.pipeline.orchestrator import PipelineExecutionResult, run_pipeline

        session = self.session

        def on_progress(pct: int, step_desc: str, log_msg: str) -> None:
            t = datetime.now().strftime("%H:%M:%S")
            session.update_progress(
                progress=pct,
                step_index=calculate_progress_step(pct),
                current_step=step_desc,
                log=f"[{t}] {log_msg}",
            )

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
            send_json_response(self, 200, {
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
            send_json_response(self, 500, {"success": False, "error": str(e)})

    def _handle_post_calculate_scores(self, payload: Dict[str, Any]) -> None:
        """Calculates preset scores based on data shape questionnaire criteria."""
        from src.pipeline.planner import PresetPlanner
        planner = getattr(self.server, "planner", None) or PresetPlanner()
        criteria = PlannerCriteria.from_dict(payload)
        scores = planner.calculate_scores(criteria=criteria)
        suggested = planner.suggest_preset_order(scores)

        send_json_response(self, 200, {
            "success": True,
            "scores": scores,
            "suggested_order": suggested,
        })

    def _handle_post_submit_plan(self, payload: Dict[str, Any]) -> None:
        """Configures, validates, and persists a DocumentPlan."""
        from src.pipeline.planner import PresetPlanner
        planner = getattr(self.server, "planner", None) or PresetPlanner()

        if "primary_preset" in payload or ("target_threshold" in payload and "steps" in payload):
            plan = DocumentPlan.from_dict(payload)
        else:
            default_doc = getattr(self.server, "default_doc", None) or self.session.pdf_path
            document_path = payload.get("document_path", "").strip() or default_doc or ""
            criteria = PlannerCriteria.from_dict(payload)
            raw_lang = payload.get("language")
            language = raw_lang.strip() if (isinstance(raw_lang, str) and raw_lang.strip() and raw_lang.strip().lower() != "none") else None
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
            "message": "Plan successfully configured and saved." if plan_file else "Plan successfully configured but not saved (no output directory).",
        }
        send_json_response(self, 200, resp_data)

        if getattr(self.server, "shutdown_on_submit", False):
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _handle_post_save_dom(self, payload: Dict[str, Any]) -> None:
        """Persists updated DocumentDOM JSON to output directory."""
        dom_data = payload.get("dom")
        output_dir = payload.get("output_dir", "output")

        if not dom_data:
            send_json_response(self, 400, {"error": "Missing dom payload"})
            return

        mkdirs(output_dir)
        dom_file = os.path.join(output_dir, "document_dom.json")
        with open(dom_file, "w", encoding="utf-8") as f:
            json.dump(dom_data, f, indent=2)

        print(f"\n[SERVER API] Saved updated DocumentDOM to '{dom_file}' ({len(dom_data.get('nodes', []))} nodes).")
        send_json_response(self, 200, {"success": True, "path": dom_file})

    def _handle_post_parse_ocr(self, payload: Dict[str, Any]) -> None:
        """Parses selected DOM section or image via OCR."""
        node_id = payload.get("node_id", "")
        image_base64 = payload.get("image_base64")
        bbox = payload.get("bbox")
        page = int(payload.get("page", 1))
        pdf_path = payload.get("pdf_path", self.session.pdf_path)
        language = payload.get("language", self.session.language)

        print(f"\n[SERVER API] Parsing selected section '{node_id}' using OCR (Lang: {language})...")

        ocr_result: Any
        if image_base64:
            ocr_result = parse_image_ocr(image_base64, language=language)
        elif pdf_path and bbox:
            ocr_result = parse_section_from_pdf(pdf_path, page, bbox, language=language)
        else:
            send_json_response(self, 400, {
                "success": False,
                "error": "Either image_base64 or (pdf_path and bbox) must be provided."
            })
            return

        response_data = {
            "success": ocr_result.get("success", False),
            "node_id": node_id,
            "text": ocr_result.get("text", ""),
            "confidence": ocr_result.get("confidence", 0.0),
            "lines": ocr_result.get("lines", []),
            "error": ocr_result.get("error"),
        }
        send_json_response(self, 200 if response_data["success"] else 422, response_data)
