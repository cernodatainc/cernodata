"""
src/pipeline/planner/server.py

Zero-dependency HTTP server for interactive in-browser data shape configuration.
Serves data_shape_config.html and accepts submitted execution plans via API endpoints.
Consolidated into unified server architecture in src/pipeline/server/.
"""

from __future__ import annotations

from typing import Any

from src.pipeline.server import (
    PipelineViewerHandler,
    PipelineViewerServer,
    ServerSessionContext,
    read_json_payload,
    send_json_response,
    serve_data_shape_wizard,
)
from src.utils import find_available_port


class DataShapeServer(PipelineViewerServer):
    """Backwards-compatible alias for PipelineViewerServer in planner wizard mode."""


class DataShapeHandler(PipelineViewerHandler):
    """Backwards-compatible request handler for planner wizard."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP access logs to keep terminal output clean."""
        return


__all__ = [
    "DataShapeHandler",
    "DataShapeServer",
    "ServerSessionContext",
    "find_available_port",
    "read_json_payload",
    "send_json_response",
    "serve_data_shape_wizard",
]
