"""
src/pipeline/planner_wizard.py

Backwards-compatibility shim forwarding to src.pipeline.planner.wizard.
"""

from __future__ import annotations

from src.pipeline.planner.wizard import (
    resolve_choice,
    run_interactive_wizard,
)

__all__ = [
    "resolve_choice",
    "run_interactive_wizard",
]
