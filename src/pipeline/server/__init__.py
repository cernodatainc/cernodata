"""
src/pipeline/server/__init__.py

Zero-dependency HTTP server, real-time pipeline execution hub, and visual viewer server.
Provides thread-safe session tracking, dynamic viewer data hydration, and interactive REST APIs.
"""

from __future__ import annotations

from src.pipeline.server.common import (
    REPO_ROOT,
    SRC_DIR,
    find_previous_runs,
    read_json_payload,
    send_json_response,
)
from src.pipeline.server.core import PipelineViewerServer
from src.pipeline.server.handler import PipelineViewerHandler
from src.pipeline.server.launcher import (
    main,
    serve_data_shape_wizard,
    start_pipeline_server,
)
from src.pipeline.server.session import ServerSessionContext
from src.utils import find_available_port, resolve_pdf_path

__all__ = [
    "SRC_DIR",
    "REPO_ROOT",
    "send_json_response",
    "read_json_payload",
    "find_previous_runs",
    "ServerSessionContext",
    "PipelineViewerServer",
    "PipelineViewerHandler",
    "serve_data_shape_wizard",
    "start_pipeline_server",
    "main",
    "find_available_port",
    "resolve_pdf_path",
]
