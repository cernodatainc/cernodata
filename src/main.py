"""
src/main.py

Main Application Entry Point.
Invokes CLI argument parsing and triggers the orchestrator pipeline.
"""

import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli import parse_args, print_summary
from src.pipeline.orchestrator import run_pipeline


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()

    print("=" * 68)
    print("cernodata: Layout-Aware Ingestion & Quality Violations Pipeline")
    print("=" * 68)
    print(f"Input Document: {args.input}")
    print(f"Language Hint: {args.language}")
    print(f"Target Confidence Threshold: {args.target_threshold}")

    if not os.path.exists(args.input):
        print(f"[ERROR] Specified input file '{args.input}' does not exist.")
        sys.exit(1)

    result = run_pipeline(
        pdf_path=args.input,
        target_threshold=args.target_threshold,
        language=args.language,
        align_skew=not args.no_align_skew,
        visualize=not args.no_visuals,
        output_dir=args.output_dir
    )

    print_summary(result)


if __name__ == "__main__":
    main()
