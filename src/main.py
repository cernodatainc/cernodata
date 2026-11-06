"""
src/main.py

Main Application Entry Point for cernodata.
Consolidates all server and pipeline CLI flags.
Running without arguments or 'python main.py' launches the interactive server.
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline.decision_tree import DEFAULT_TARGET_CONFIDENCE_THRESHOLD
from src.pipeline.orchestrator import run_pipeline
from src.pipeline.planner import DocumentPlan, PresetPlanner


def create_parser() -> argparse.ArgumentParser:
    """Creates and returns the consolidated argument parser for cernodata."""
    parser = argparse.ArgumentParser(
        prog="cernodata",
        description="cernodata: Document Ingestion Hub, Preset Planner, and Interactive Server.",
    )

    # Server Configuration Flags
    parser.add_argument(
        "--port", "-p", "--browser-port",
        type=int,
        default=8000,
        dest="port",
        help="Port to serve interactive server hub and visual viewer (default: 8000).",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host network interface to bind the server (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically launch web browser on startup.",
    )
    parser.add_argument(
        "--serve", "-s",
        action="store_true",
        default=True,
        help="Start the live HTTP server (default behavior).",
    )

    # Document & Ingestion Flags
    parser.add_argument(
        "--input", "--pdf", "-i",
        type=str,
        default=None,
        dest="input",
        help="Path to input PDF document.",
    )
    parser.add_argument(
        "--language", "-l",
        type=str,
        default="en",
        help="Language hint code for OCR and quality verification (e.g. 'pl', 'de', 'en').",
    )
    parser.add_argument(
        "--target-threshold", "-t",
        type=float,
        default=DEFAULT_TARGET_CONFIDENCE_THRESHOLD,
        help=f"Target confidence threshold (default: {DEFAULT_TARGET_CONFIDENCE_THRESHOLD}).",
    )
    parser.add_argument(
        "--override-preset", "--preset",
        type=str,
        default=None,
        dest="override_preset",
        help="Explicitly override primary preset (e.g. 'docling_fast', 'docling_deep', 'vision_llm_direct').",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="output",
        help="Directory to store JSON DOM, violations report, and rendered overlay images (default: output).",
    )
    parser.add_argument(
        "--no-align-skew",
        action="store_true",
        help="Disable automatic local text alignment skew detection.",
    )
    parser.add_argument(
        "--no-visuals",
        action="store_true",
        help="Disable visual bounding box overlay rendering.",
    )

    # Execution Mode & Planner Flags
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run pipeline in headless batch CLI mode instead of launching the interactive server.",
    )
    parser.add_argument(
        "--plan",
        type=str,
        default=None,
        help="Path to execution plan JSON file (e.g. output/plan.json).",
    )
    parser.add_argument(
        "--create-plan",
        action="store_true",
        help="Launch interactive planner questionnaire to configure preset ranking and execution plan.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Generate and save execution plan without running pipeline.",
    )
    parser.add_argument(
        "--cli", "--terminal",
        action="store_true",
        dest="cli",
        help="Force terminal-based CLI questionnaire instead of browser-based data shape configuration.",
    )
    parser.add_argument(
        "--view", "-v",
        action="store_true",
        help="Automatically open interactive HTML web viewer in default browser after batch execution.",
    )

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parses and validates command-line arguments, ensuring backwards compatibility."""
    parser = create_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "browser_port") or getattr(args, "browser_port", None) is None:
        args.browser_port = args.port
    return args


class CliProgressReporter:
    """Terminal progress spinner and milestone reporter for CLI pipeline execution."""

    def __init__(self) -> None:
        self.spinner_chars: list[str] = ["|", "/", "-", "\\"]
        self.spinner_idx: int = 0

    def __call__(self, pct: int, step_desc: str, log_msg: str) -> None:
        char = self.spinner_chars[self.spinner_idx % len(self.spinner_chars)]
        self.spinner_idx += 1
        sys.stdout.write(f"\r[{char}] [{pct:3d}%] {step_desc}\n")
        sys.stdout.flush()


def main(argv: list[str] | None = None) -> None:
    """Main CLI entrypoint. Default invocation starts interactive pipeline server."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

    args = parse_args(argv)

    active_plan = None
    if args.create_plan:
        planner = PresetPlanner()
        if getattr(args, "cli", False):
            active_plan = planner.interactive_session(default_doc=args.input)
        else:
            active_plan = planner.browser_session(
                default_doc=args.input,
                default_lang=args.language,
                default_threshold=args.target_threshold,
                output_dir=args.output_dir,
                port=args.port,
                open_browser=not getattr(args, "no_browser", False),
            )
        if args.override_preset:
            active_plan.apply_preset_override(args.override_preset)
        plan_path = os.path.join(args.output_dir, "plan.json")
        active_plan.save(plan_path)
        print(f"\n[OK] Plan saved to '{plan_path}'.")
        if getattr(args, "plan_only", False):
            return
        if not getattr(args, "batch", False):
            from src.pipeline.server import start_pipeline_server
            start_pipeline_server(
                pdf_path=active_plan.document_path or args.input or "",
                language=(active_plan.language or args.language or "en"),
                port=args.port,
                open_browser=not getattr(args, "no_browser", False),
            )
            return
        print("Proceeding to batch pipeline execution...\n")
    elif args.plan:
        if not os.path.exists(args.plan):
            print(f"[ERROR] Specified plan file '{args.plan}' does not exist.")
            sys.exit(1)
        active_plan = DocumentPlan.load(args.plan)
        if args.override_preset:
            active_plan.apply_preset_override(args.override_preset)

    # Unless headless batch mode is explicitly requested, running main.py starts the server hub.
    # "python main.py" just starts the server.
    if not getattr(args, "batch", False):
        from src.pipeline.server import start_pipeline_server
        initial_doc = args.input or (active_plan.document_path if active_plan else "") or ""
        initial_lang = (active_plan.language if active_plan and active_plan.language else args.language) or "en"
        start_pipeline_server(
            pdf_path=initial_doc,
            language=initial_lang,
            port=args.port,
            open_browser=not getattr(args, "no_browser", False),
        )
        return

    # Headless / Batch pipeline execution (--batch)
    doc_input = args.input or (active_plan.document_path if active_plan else None)
    if not doc_input:
        print("[ERROR] Input document path is required for batch mode (--input / -i or via plan).")
        sys.exit(1)

    print("=" * 68)
    print("cernodata: Layout-Aware Ingestion & Quality Violations Pipeline")
    print("=" * 68)
    print(f"Input Document: {doc_input}")
    if active_plan:
        print(f"Executing Plan: Primary Preset '{active_plan.primary_preset}', Threshold {active_plan.target_threshold}")
    else:
        print(f"Language Hint: {args.language}")
        print(f"Target Confidence Threshold: {args.target_threshold}")

    if not os.path.exists(doc_input):
        print(f"[ERROR] Specified input file '{doc_input}' does not exist.")
        sys.exit(1)

    progress_reporter = CliProgressReporter()
    result = run_pipeline(
        pdf_path=doc_input,
        target_threshold=args.target_threshold,
        language=args.language,
        preset=args.override_preset or "docling_fast",
        align_skew=not args.no_align_skew,
        visualize=not args.no_visuals,
        output_dir=args.output_dir,
        plan=active_plan,
        progress_callback=progress_reporter,
    )

    from src.cli import print_summary
    print_summary(result)

    viewer_path = result.get("html_viewer_path")
    if getattr(args, "view", False) and viewer_path:
        viewer_uri = "file:///" + os.path.abspath(viewer_path).replace("\\", "/")
        print(f"\n[VIEW] Opening interactive viewer in default browser: {viewer_uri}")
        webbrowser.open(viewer_uri)


if __name__ == "__main__":
    main()
