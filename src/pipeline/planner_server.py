"""
src/pipeline/planner_server.py

Zero-dependency HTTP server for interactive in-browser data shape configuration.
Serves data_shape_config.html and accepts submitted execution plans via API endpoints.
Consolidated into unified server architecture in src/pipeline/server.py.
"""

from __future__ import annotations

from typing import Any

from src.utils import find_available_port
from src.pipeline.server import (
    PipelineViewerServer,
    PipelineViewerHandler,
    ServerSessionContext,
    send_json_response,
    read_json_payload,
    serve_data_shape_wizard,
)


class DataShapeServer(PipelineViewerServer):
    """Backwards-compatible alias for PipelineViewerServer in planner wizard mode."""
    pass


class DataShapeHandler(PipelineViewerHandler):
    """Backwards-compatible request handler for planner wizard."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP access logs to keep terminal output clean."""
        return


__all__ = [
    "DataShapeServer",
    "DataShapeHandler",
    "ServerSessionContext",
    "find_available_port",
    "serve_data_shape_wizard",
    "send_json_response",
    "read_json_payload",
]
