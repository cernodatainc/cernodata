"""
src/dependency_graph.py

Architectural dependency visualizer and silo invariant validator.
Forwards to the canonical implementation in src.meta_checks.visualize_dependencies.
"""

from __future__ import annotations

import sys
from src.meta_checks.visualize_dependencies import (
    build_dependency_graph,
    extract_internal_imports,
    generate_dot_graph,
    main,
    verify_planner_silo,
)

__all__ = [
    "build_dependency_graph",
    "extract_internal_imports",
    "generate_dot_graph",
    "verify_planner_silo",
    "main",
]

if __name__ == "__main__":
    sys.exit(main())
