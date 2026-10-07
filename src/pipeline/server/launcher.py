"""
src/pipeline/server/launcher.py

Entry points for launching the pipeline viewer hub and standalone data shape wizard.
"""

from __future__ import annotations

import argparse
import os
import webbrowser
from typing import Any, List, Optional

from src.pipeline.planner.models import DocumentPlan
from src.pipeline.server.common import (
    SRC_DIR,
    copy_file_if_exists,
    read_html_template,
)
from src.pipeline.server.core import PipelineViewerServer
from src.pipeline.server.handler import PipelineViewerHandler
from src.pipeline.server.session import ServerSessionContext
from src.utils import find_available_port, mkdirs


def print_banner(lines: List[str]) -> None:
    """Prints a standardized server startup banner."""
    sep = "=" * 68
    print(sep, flush=True)
    for line in lines:
        print(line, flush=True)
    print(sep, flush=True)


def export_standalone_wizard_assets(output_dir: str, html_content: str) -> None:
    """Exports standalone copies of HTML, CSS, and JS assets to target directory for offline usage."""
    from src.visualization.bundler import get_data_shape_config_js

    mkdirs(output_dir)
    exported_html_path = os.path.join(output_dir, "data_shape_config.html")
    with open(exported_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    exported_js_path = os.path.join(output_dir, "data_shape_config.js")
    with open(exported_js_path, "w", encoding="utf-8") as f:
        f.write(get_data_shape_config_js())

    css_src = os.path.join(SRC_DIR, "visualization", "data_shape_config.css")
    css_dst = os.path.join(output_dir, "data_shape_config.css")
    copy_file_if_exists(css_src, css_dst)


def serve_data_shape_wizard(
    planner: Any,
    default_doc: Optional[str] = None,
    default_lang: Optional[str] = None,
    default_threshold: float = 0.82,
    output_dir: str = "output",
    port: int = 8000,
    open_browser: bool = True,
) -> DocumentPlan:
    """
    Serves interactive HTML questionnaire in browser to configure data shape parameters.
    Blocks until user submits plan via browser, then shuts down and returns DocumentPlan.
    """
    actual_port = find_available_port(start_port=port)
    html_content = read_html_template("data_shape_config.html", fallback_title="cernodata Data Shape Planner")
    export_standalone_wizard_assets(output_dir=output_dir, html_content=html_content)

    session = ServerSessionContext(pdf_path=default_doc or "", language=default_lang or "en", output_dir=output_dir)
    httpd = PipelineViewerServer(("127.0.0.1", actual_port), PipelineViewerHandler, session_context=session)
    httpd.shutdown_on_submit = True
    httpd.planner = planner
    httpd.default_doc = default_doc
    httpd.default_lang = default_lang
    httpd.default_threshold = default_threshold
    httpd.output_dir = output_dir
    httpd.html_content = html_content

    url = f"http://127.0.0.1:{actual_port}/data_shape_config.html"

    print_banner([
        "cernodata: Interactive Data Shape & Preset Planner",
        f"Serving data shape questionnaire at: {url}",
        "Awaiting configuration in browser... (Press Ctrl+C to abort)",
    ])

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        print("\n[SERVER] Data shape session interrupted by user.")
        httpd.server_close()
        raise

    httpd.server_close()

    if httpd.submitted_plan is not None:
        return httpd.submitted_plan

    # Fallback if somehow exited without plan
    return planner.create_plan(
        document_path=default_doc or "",
        language=default_lang,
        target_threshold=default_threshold,
    )


def start_pipeline_server(
    pdf_path: str = "",
    language: str = "en",
    port: int = 8000,
    open_browser: bool = True,
) -> None:
    """Starts local multi-threaded HTTP server and opens interactive hub landing page in default web browser."""
    actual_port = find_available_port(start_port=port)
    session = ServerSessionContext(pdf_path=pdf_path, language=language)
    PipelineViewerHandler._default_session = session

    server_address = ("", actual_port)
    httpd = PipelineViewerServer(server_address, PipelineViewerHandler, session_context=session)
    url = f"http://localhost:{actual_port}/"

    print_banner([
        f"cernodata Ingestion Hub & Visual Server running at {url}",
        f"Dashboard Landing Page: {url}",
        f"Interactive Visual Flow Viewer: {url}viewer",
        f"Backend Hydration API: {url}api/viewer_data",
    ])

    if open_browser:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Stopping pipeline server.")
        httpd.server_close()


def main() -> None:
    """CLI entrypoint for standalone pipeline server."""
    parser = argparse.ArgumentParser(
        description="cernodata: Document Ingestion Hub, Preset Planner and Interactive Visual Viewer Server."
    )
    parser.add_argument("--pdf", "--input", "-i", type=str, default="", help="Path to initial PDF document")
    parser.add_argument("--language", "-l", type=str, default="en", help="Default language hint code (e.g. 'pl', 'en')")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically launch web browser")
    args = parser.parse_args()

    start_pipeline_server(
        pdf_path=args.pdf,
        language=args.language,
        port=args.port,
        open_browser=not args.no_browser,
    )
