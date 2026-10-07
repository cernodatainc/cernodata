"""
src/pipeline/server/core.py

Multi-threaded HTTP server implementation for cernodata pipeline and viewer.
"""

from __future__ import annotations

import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional, Tuple, Type

from src.pipeline.planner.models import DocumentPlan
from src.pipeline.server.session import ServerSessionContext

logger = logging.getLogger("cernodata.server.core")


class PipelineViewerServer(ThreadingHTTPServer):
    """Multi-threaded HTTP server managing background pipeline executor and session context."""

    session_context: ServerSessionContext
    executor: ThreadPoolExecutor
    shutdown_on_submit: bool = False
    html_content: str = ""
    default_doc: Optional[str] = None
    default_lang: Optional[str] = None
    default_threshold: float = 0.85
    output_dir: str = "output"
    planner: Any = None

    def __init__(
        self,
        server_address: Tuple[str, int],
        RequestHandlerClass: Type[SimpleHTTPRequestHandler],
        session_context: Optional[ServerSessionContext] = None,
        max_workers: int = 4,
    ) -> None:
        super().__init__(server_address, RequestHandlerClass)
        self.session_context = session_context or ServerSessionContext()
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cernodata-worker")

    @property
    def submitted_plan(self) -> Optional[DocumentPlan]:
        return self.session_context.submitted_plan

    @submitted_plan.setter
    def submitted_plan(self, value: Optional[DocumentPlan]) -> None:
        self.session_context.submitted_plan = value

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Suppresses tracebacks for normal client socket aborts and resets."""
        exc_type, exc_val, _ = sys.exc_info()
        if exc_type in (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            logger.debug("Client %s disconnected abruptly: %s", client_address, exc_val)
            return
        super().handle_error(request, client_address)

    def server_close(self) -> None:
        if hasattr(self, "executor"):
            self.executor.shutdown(wait=False, cancel_futures=True)
        super().server_close()
