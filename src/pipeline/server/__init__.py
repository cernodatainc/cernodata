"""
src/pipeline/server/__init__.py

Zero-dependency HTTP server, real-time pipeline execution hub, and visual viewer server.
Provides thread-safe session tracking, dynamic viewer data hydration, and interactive REST APIs.
"""

from __future__ import annotations

from src.pipeline.server.common import (
    REPO_ROOT,
    SRC_DIR,
    build_runs_grid,
    build_viewer_dataset,
    calculate_progress_step,
    copy_file_if_exists,
    create_preset_attempt_record,
    find_previous_runs,
    load_or_render_page_images,
    load_run_artifacts,
    normalize_violations,
    read_html_template,
    read_json_payload,
    safe_load_json,
    send_file_response,
    send_first_existing_file,
    send_html_response,
    send_json_response,
    send_response_bytes,
    send_text_response,
)
from src.pipeline.server.core import PipelineViewerServer
from src.pipeline.server.handler import PipelineViewerHandler
from src.pipeline.server.launcher import (
    export_standalone_wizard_assets,
    main,
    print_banner,
    serve_data_shape_wizard,
    start_pipeline_server,
)
from src.pipeline.server.session import ServerSessionContext
from src.utils import find_available_port, resolve_pdf_path

__all__ = [
    "SRC_DIR",
    "REPO_ROOT",
    "send_response_bytes",
    "send_json_response",
    "read_json_payload",
    "send_text_response",
    "send_html_response",
    "send_file_response",
    "send_first_existing_file",
    "copy_file_if_exists",
    "read_html_template",
    "safe_load_json",
    "normalize_violations",
    "load_run_artifacts",
    "load_or_render_page_images",
    "calculate_progress_step",
    "create_preset_attempt_record",
    "build_viewer_dataset",
    "build_runs_grid",
    "find_previous_runs",
    "ServerSessionContext",
    "PipelineViewerServer",
    "PipelineViewerHandler",
    "export_standalone_wizard_assets",
    "print_banner",
    "serve_data_shape_wizard",
    "start_pipeline_server",
    "main",
    "find_available_port",
    "resolve_pdf_path",
]
