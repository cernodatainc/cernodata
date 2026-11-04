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
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

from src.pipeline.server.http_utils import (
    SRC_DIR,
    read_json_payload,
    send_file_response,
    send_json_response,
    send_text_response,
)
from src.pipeline.server.routes import ApiRoutesMixin
from src.pipeline.server.routes_static import StaticRoutesMixin
from src.pipeline.server.router import api_router
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

    # -------------------------------------------------------------------------
    # Route Dispatchers: do_GET and do_POST
    # -------------------------------------------------------------------------

    def do_GET(self) -> None:
        """Dispatches GET requests to appropriate static views or JSON APIs."""
        parsed_url = urlparse(self.path)
        raw_path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        if api_router.dispatch_get(self, raw_path, query_params):
            return

        static_files: Dict[str, tuple[str, str, str]] = {
            "/viewer.css": (os.path.join(SRC_DIR, "visualization", "viewer", "viewer.css"), "text/css; charset=utf-8", "CSS asset not found"),
            "/landing.css": (os.path.join(SRC_DIR, "visualization", "landing.css"), "text/css; charset=utf-8", "Landing CSS asset not found"),
            "landing.css": (os.path.join(SRC_DIR, "visualization", "landing.css"), "text/css; charset=utf-8", "Landing CSS asset not found"),
            "/favicon.svg": (os.path.join(SRC_DIR, "visualization", "favicon.svg"), "image/svg+xml", "Favicon not found"),
            "/favicon.ico": (os.path.join(SRC_DIR, "visualization", "favicon.svg"), "image/svg+xml", "Favicon not found"),
        }
        if raw_path in static_files:
            fpath, ctype, err_msg = static_files[raw_path]
            if not send_file_response(self, fpath, ctype):
                self.send_error(404, err_msg)
            return

        if raw_path in ("/viewer.js", "/landing.js", "landing.js", "/data_shape_config.js", "data_shape_config.js"):
            from src.visualization.bundler import get_data_shape_config_js, get_landing_js, get_viewer_js
            js_map: Dict[str, Callable[[], str]] = {
                "/viewer.js": get_viewer_js,
                "/landing.js": get_landing_js,
                "landing.js": get_landing_js,
                "/data_shape_config.js": get_data_shape_config_js,
                "data_shape_config.js": get_data_shape_config_js,
            }
            send_text_response(self, js_map[raw_path](), content_type="application/javascript; charset=utf-8")
            return

        if raw_path in ("", "/", "/index.html", "/landing", "/hub"):
            self._serve_landing_page()
        elif raw_path == "/viewer.html":
            self._serve_viewer_html()
        elif raw_path == "/interactive_viewer.html":
            self._serve_interactive_viewer_compat()
        elif raw_path in ("/data_shape_config.css", "data_shape_config.css"):
            self._serve_data_shape_asset(
                "data_shape_config.css", "text/css; charset=utf-8", "Data shape config CSS asset not found"
            )
        elif raw_path in ("/data_shape_config.html", "/data_shape", "/planner"):
            self._serve_planner_page()
        elif raw_path == "/api/config":
            self._handle_api_config()
        elif raw_path in ("/api/previous_runs", "/api/runs"):
            runs = self.session.get_previous_runs()
            active_run = self.session.output_dir
            if (active_run == "output" or not active_run) and runs:
                target_full = os.path.join(self.session.repo_root, "output")
                if not os.path.exists(target_full) and runs[0].get("dir_path"):
                    active_run = str(runs[0]["dir_path"])
            send_json_response(self, 200, {"runs": runs, "active_run": active_run})
        elif raw_path == "/api/load_run":
            self._handle_load_run(query_params.get("output_dir", [""])[0])
        elif raw_path == "/api/documents":
            send_json_response(self, 200, {"documents": self.session.get_available_documents()})
        elif raw_path == "/api/file_run_mappings":
            send_json_response(self, 200, self.session.get_file_run_mappings())
        elif raw_path == "/api/progress":
            send_json_response(self, 200, self.session.get_progress())
        elif raw_path == "/api/results":
            res_target_dir: Optional[str] = query_params.get("output_dir", [""])[0] or None
            try:
                send_json_response(self, 200, self.session.get_results(output_dir=res_target_dir))
            except Exception as e:
                logger.warning("Results retrieval failed for '%s': %s", res_target_dir, e)
                send_json_response(self, 500, {"error": str(e), "attempts": [], "decision": None, "violations": []})
        elif raw_path == "/api/viewer_data":
            v_target_dir: Optional[str] = query_params.get("output_dir", [""])[0] or None
            try:
                send_json_response(self, 200, self.session.get_viewer_data(output_dir=v_target_dir))
            except (ValueError, FileNotFoundError) as e:
                logger.info("Viewer data unavailable for '%s': %s", v_target_dir or self.session.output_dir, e)
                send_json_response(self, 404, {"error": str(e), "viewer_data": None})
            except Exception as e:
                logger.error("Unexpected error retrieving viewer data: %s", e)
                send_json_response(self, 500, {"error": str(e)})
        elif raw_path in ("/api/ocr_engines", "/api/engines"):
            self._handle_get_ocr_engines()
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
        raw_path = urlparse(self.path).path
        payload = read_json_payload(self)

        if api_router.dispatch_post(self, raw_path, payload):
            return

        if raw_path == "/api/load_run":
            self._handle_load_run(payload.get("output_dir") or payload.get("run_id") or "output")
            return

        post_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {
            "/api/remove_run": self._handle_post_remove_run,
            "/api/run": self._handle_post_run,
            "/api/rerun": self._handle_post_rerun,
            "/api/calculate_scores": self._handle_post_calculate_scores,
            "/api/submit_plan": self._handle_post_submit_plan,
            "/api/save_dom": self._handle_post_save_dom,
            "/api/parse_section_ocr": self._handle_post_parse_ocr,
            "/api/ocr_section": self._handle_post_parse_ocr,
            "/api/documents": self._handle_post_add_document,
            "/api/add_file": self._handle_post_add_document,
            "/api/upload": self._handle_post_add_document,
            "/api/open_file_dialog": self._handle_post_open_file_dialog,
            "/api/browse_files": self._handle_post_open_file_dialog,
        }
        handler_fn = post_handlers.get(raw_path)
        if handler_fn is not None:
            handler_fn(payload)
        else:
            self.send_error(404, f"Endpoint not found: {raw_path}")

