"""
src/main.py

Main Application Entry Point.
Invokes CLI argument parsing, interactive plan creation, plan-driven pipeline execution,
or live server preview.
"""

import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli import parse_args, print_summary
from src.pipeline.orchestrator import run_pipeline
from src.pipeline.planner import PresetPlanner, DocumentPlan


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()

    active_plan = None
    if args.create_plan:
        planner = PresetPlanner()
        active_plan = planner.interactive_session(default_doc=args.input)
        if args.override_preset:
            active_plan.primary_preset = args.override_preset
            active_plan.overridden = True
            active_plan.preset_order = [args.override_preset] + [p for p in active_plan.preset_order if p != args.override_preset]
        plan_path = os.path.join(args.output_dir, "plan.json")
        active_plan.save(plan_path)
        print(f"\n[OK] Plan saved to '{plan_path}'.")
        if getattr(args, "plan_only", False):
            return
        print("Proceeding to pipeline execution...\n")
    elif args.plan:
        if not os.path.exists(args.plan):
            print(f"[ERROR] Specified plan file '{args.plan}' does not exist.")
            sys.exit(1)
        active_plan = DocumentPlan.load(args.plan)
        if args.override_preset:
            active_plan.primary_preset = args.override_preset
            active_plan.overridden = True
            active_plan.preset_order = [args.override_preset] + [p for p in active_plan.preset_order if p != args.override_preset]

    doc_input = args.input or (active_plan.document_path if active_plan else None)
    if not doc_input:
        print("[ERROR] Input document path is required (--input / -i or via plan).")
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

    result = run_pipeline(
        pdf_path=doc_input,
        target_threshold=args.target_threshold,
        language=args.language,
        preset=args.override_preset or "docling_fast",
        align_skew=not args.no_align_skew,
        visualize=not args.no_visuals,
        output_dir=args.output_dir,
        plan=active_plan
    )

    print_summary(result)

    if getattr(args, "view", False) and result.get("html_viewer_path"):
        viewer_uri = "file:///" + os.path.abspath(result["html_viewer_path"]).replace("\\", "/")
        print(f"\n[VIEW] Opening interactive viewer in default browser: {viewer_uri}")
        webbrowser.open(viewer_uri)

    if getattr(args, "serve", False):
        from src.pipeline.server import start_pipeline_server
        start_pipeline_server(
            pdf_path=doc_input,
            language=active_plan.language if active_plan else args.language
        )


if __name__ == "__main__":
    main()
