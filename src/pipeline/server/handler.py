"""
src/pipeline/server/handler.py

HTTP request handler serving landing page, viewer assets, hydration API, and execution endpoints.
Composes modular static and API route mixins.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import parse_qs, urlparse

from src.pipeline.execution_models import AttemptRecord
from src.pipeline.server.artifacts import ViewerDataset
from src.pipeline.server.http_utils import (
    SRC_DIR,
    read_json_payload,
    send_file_response,
    send_json_response,
    send_text_response,
)
from src.pipeline.server.routes import ApiRoutesMixin
from src.pipeline.server.routes_static import StaticRoutesMixin
from src.pipeline.server.session import ServerSessionContext

logger = logging.getLogger("cernodata.server.handler")


class PipelineViewerHandler(StaticRoutesMixin, ApiRoutesMixin, SimpleHTTPRequestHandler):
    """
    HTTP request handler serving interactive landing page, viewer assets,
    hydration API, and execution endpoints.
    """

    def log_message(self, format: str, *args: Any) -> None:
        """Suppresses standard HTTP access logs to keep terminal output clean."""
        logger.debug("%s - " + format, self.address_string(), *args)

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
    viewer_data: Optional[ViewerDataset] = None
    current_result: Optional[Dict[str, Any]] = None
    preset_attempts: List[AttemptRecord] = []
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
    def _sync_default_session_state(cls) -> None:
        """Synchronizes legacy handler class attributes with the default session context."""
        cls.pdf_path = cls._default_session.pdf_path
        cls.language = cls._default_session.language
        cls.viewer_data = cls._default_session.viewer_data
        cls.current_result = cls._default_session.current_result
        cls.preset_attempts = cls._default_session.preset_attempts

    @classmethod
    def load_previous_run(cls, output_dir: str) -> Dict[str, Any]:
        """Loads and switches default session to an existing output directory."""
        res = cls._default_session.load_previous_run(output_dir)
        cls._sync_default_session_state()
        return res

    @classmethod
    def get_viewer_data(cls) -> ViewerDataset:
        """Returns structured data required to hydrate the interactive visual viewer."""
        return cls._default_session.get_viewer_data()

    @classmethod
    def update_result_state(cls, result: Mapping[str, Any], pdf_path: str, language: str) -> None:
        """Updates server memory state and hydration dataset from run_pipeline result."""
        cls._default_session.update_result_state(result, pdf_path, language)
        cls._sync_default_session_state()

    @classmethod
    def get_cached_preset_result(cls, pdf_path: str, preset: str, language: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves cached preset result delegating to default session."""
        return cls._default_session.get_cached_preset_result(pdf_path, preset, language)

    # -------------------------------------------------------------------------
    # Route Dispatchers: do_GET and do_POST
    # -------------------------------------------------------------------------

    def do_GET(self) -> None:
        """Dispatches GET requests to appropriate static views or JSON APIs."""
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
            from src.visualization.bundler import get_landing_js
            send_text_response(self, get_landing_js(), content_type="application/javascript; charset=utf-8")
        elif raw_path in ("/data_shape_config.css", "data_shape_config.css"):
            self._serve_data_shape_asset(
                "data_shape_config.css", "text/css; charset=utf-8", "Data shape config CSS asset not found"
            )
        elif raw_path in ("/data_shape_config.js", "data_shape_config.js"):
            from src.visualization.bundler import get_data_shape_config_js
            send_text_response(self, get_data_shape_config_js(), content_type="application/javascript; charset=utf-8")
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
        elif raw_path == "/api/runs_grid":
            target_doc: Optional[str] = (
                query_params.get("document", [""])[0]
                or query_params.get("file", [""])[0]
                or None
            )
            send_json_response(self, 200, self.session.get_runs_grid(document_name=target_doc))
        else:
            self.send_error(404, f"Endpoint not found: {raw_path}")

    def do_POST(self) -> None:
        """Dispatches POST requests with parsed JSON payloads to execution handlers."""
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
