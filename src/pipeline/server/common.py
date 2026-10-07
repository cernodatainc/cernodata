"""
src/pipeline/server/common.py

Unified re-export facade for server HTTP transport utilities, artifact loaders,
and workspace run discovery.

For domain-specific implementations, see:
- src.pipeline.server.http_utils: Low-level HTTP writers, readers, and templates.
- src.pipeline.server.artifacts: Artifact loading, normalization, and visual datasets.
- src.pipeline.server.discovery: Workspace scanning and runs matrix grid generation.
"""

from __future__ import annotations

from src.pipeline.server.artifacts import (
    build_viewer_dataset,
    calculate_progress_step,
    create_preset_attempt_record,
    extract_decision_from_html,
    load_or_render_page_images,
    load_run_artifacts,
    normalize_violations,
    safe_load_json,
)
from src.pipeline.server.discovery import (
    build_runs_grid,
    find_previous_runs,
)
from src.pipeline.server.http_utils import (
    REPO_ROOT,
    SRC_DIR,
    copy_file_if_exists,
    read_html_template,
    read_json_payload,
    send_file_response,
    send_first_existing_file,
    send_html_response,
    send_json_response,
    send_response_bytes,
    send_text_response,
)

__all__ = [
    "REPO_ROOT",
    "SRC_DIR",
    "build_runs_grid",
    "build_viewer_dataset",
    "calculate_progress_step",
    "copy_file_if_exists",
    "create_preset_attempt_record",
    "extract_decision_from_html",
    "find_previous_runs",
    "load_or_render_page_images",
    "load_run_artifacts",
    "normalize_violations",
    "read_html_template",
    "read_json_payload",
    "safe_load_json",
    "send_file_response",
    "send_first_existing_file",
    "send_html_response",
    "send_json_response",
    "send_response_bytes",
    "send_text_response",
]
