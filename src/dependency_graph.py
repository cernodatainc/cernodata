"""
src/dependency_graph.py

Graphviz DOT dependency visualizer and architectural silo invariant validator.
Extracts AST-level internal dependencies across the codebase, verifies that
planner is strictly siloed from orchestrator and viewer, and exports Graphviz DOT graphs.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


def extract_internal_imports(file_path: Path, repo_root: Path) -> Set[str]:
    """Parses a Python file and returns a set of imported internal module paths."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except Exception:
        return set()

    imported: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("src.") or alias.name == "src":
                    imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module
            if mod and (mod.startswith("src.") or mod == "src"):
                imported.add(mod)
            elif node.level and node.level > 0:
                pkg_parts = list(file_path.relative_to(repo_root).parts)[:-1]
                steps = node.level - 1
                if steps <= len(pkg_parts):
                    base = ".".join(pkg_parts[: len(pkg_parts) - steps])
                    resolved = f"{base}.{mod}" if mod else base
                    if resolved.startswith("src"):
                        imported.add(resolved)
    return imported


def build_dependency_graph(repo_root: Path) -> Dict[str, Set[str]]:
    """Constructs a directed module dependency mapping for all source files in src/."""
    graph: Dict[str, Set[str]] = {}
    for py_file in (repo_root / "src").rglob("*.py"):
        if "tests" in py_file.parts or "__pycache__" in py_file.parts:
            continue
        parts = list(py_file.relative_to(repo_root).parts)
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        if parts[-1] == "__init__":
            parts = parts[:-1]
        mod_id = ".".join(parts)
        graph[mod_id] = extract_internal_imports(py_file, repo_root)
    return graph


def verify_planner_silo(graph: Dict[str, Set[str]]) -> List[str]:
    """Verifies that planner modules are strictly siloed from orchestrator and viewer."""
    violations: List[str] = []
    for mod_id, dependencies in graph.items():
        is_planner = mod_id == "src.pipeline.planner" or mod_id.startswith("src.pipeline.planner.")
        if not is_planner:
            continue
        for dep in dependencies:
            if "orchestrator" in dep:
                violations.append(f"Silo Violation: '{mod_id}' imports orchestrator module '{dep}'")
            if "visualization" in dep:
                violations.append(f"Silo Violation: '{mod_id}' imports visualization module '{dep}'")
            if "src.pipeline.server" in dep:
                violations.append(f"Silo Violation: '{mod_id}' imports server/viewer module '{dep}'")
    return violations


def generate_dot_graph(graph: Dict[str, Set[str]], title: str = "cernodata Dependency Graph") -> str:
    """Generates a Graphviz DOT representation of the dependency graph with subsystem clusters."""
    lines: List[str] = [
        'digraph "cernodata_dependencies" {',
        '    rankdir="TB";',
        '    splines=ortho;',
        '    node [shape=box, style="rounded,filled", fontname="Segoe UI, Helvetica, Arial", fontsize=10];',
        '    edge [fontname="Segoe UI, Helvetica, Arial", fontsize=8, color="#64748B"];',
        f'    label="{title}";',
        '    labelloc="t";',
        '    fontsize=14;\n',
    ]

    clusters: Dict[str, List[str]] = {k: [] for k in ["planner", "parsers", "orchestrator", "server", "visualization", "core_dom", "other"]}
    for mod in sorted(graph.keys()):
        if mod.startswith("src.pipeline.planner"):
            clusters["planner"].append(mod)
        elif mod.startswith("src.pipeline.parsers") or mod.startswith("src.parsers"):
            clusters["parsers"].append(mod)
        elif mod.startswith("src.pipeline.server") or mod.startswith("src.pipeline.routes") or mod.startswith("src.pipeline.session"):
            clusters["server"].append(mod)
        elif mod.startswith("src.visualization"):
            clusters["visualization"].append(mod)
        elif any(k in mod for k in ("orchestrator", "fallback", "attempt", "artifact", "config_resolver")):
            clusters["orchestrator"].append(mod)
        elif any(mod.startswith(k) for k in ("src.dom", "src.decision_tree", "src.heuristics", "src.quality")):
            clusters["core_dom"].append(mod)
        else:
            clusters["other"].append(mod)

    cluster_meta: Dict[str, Tuple[str, str, str]] = {
        "planner": ("cluster_planner", "Preset Planner (Siloed Subsystem)", "#E0F2FE"),
        "parsers": ("cluster_parsers", "Parser Dispatch & Presets", "#FEF3C7"),
        "orchestrator": ("cluster_orchestrator", "Pipeline Orchestration", "#F1F5F9"),
        "server": ("cluster_server", "Interactive Server & REST Routes", "#DCFCE7"),
        "visualization": ("cluster_visualization", "Visual Viewer & Bundler", "#F3E8FF"),
        "core_dom": ("cluster_core_dom", "Core DOM & Quality Evaluation", "#FFE4E6"),
        "other": ("cluster_other", "Utilities & Entrypoints", "#F8FAFC"),
    }

    for key, (cluster_id, label, fill_color) in cluster_meta.items():
        mods = clusters.get(key, [])
        if not mods:
            continue
        lines.append(f'    subgraph "{cluster_id}" {{\n        label="{label}";\n        style="filled,rounded";\n        fillcolor="{fill_color}";\n        color="#94A3B8";\n')
        for m in mods:
            lines.append(f'        "{m}" [label="{m.replace("src.", "")}", fillcolor="#FFFFFF", color="#CBD5E1"];')
        lines.append("    }\n")

    lines.append("    # Dependency Edges")
    for src_mod, deps in sorted(graph.items()):
        for dep in sorted(deps):
            target = dep if dep in graph else next((c for c in graph if dep.startswith(c)), None)
            if target and target != src_mod:
                is_planner = src_mod.startswith("src.pipeline.planner")
                is_illegal = any(k in target for k in ("orchestrator", "server", "visualization"))
                if is_planner and is_illegal:
                    lines.append(f'    "{src_mod}" -> "{target}" [color="#DC2626", penwidth=2.5, style="dashed", label="VIOLATION"];')
                else:
                    lines.append(f'    "{src_mod}" -> "{target}";')
    lines.append("}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dependency graph and verify subsystem silos.")
    parser.add_argument("--repo-root", default=None, help="Path to repository root")
    parser.add_argument("--dot-out", default=None, help="Target path to write .dot output file")
    parser.add_argument("--check-silos", action="store_true", help="Exit with non-zero if silo invariants are violated")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parents[1]
    graph = build_dependency_graph(repo_root)
    violations = verify_planner_silo(graph)
    dot_content = generate_dot_graph(graph)

    output_path = args.dot_out or str(repo_root / "test_output" / "dependency_graph.dot")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(dot_content)

    print(f"Generated dependency DOT graph at: {output_path} ({len(graph)} modules)")
    if violations:
        print(f"\n[FAIL] Found {len(violations)} Silo Violations:")
        for v in violations:
            print(f"  - {v}")
        if args.check_silos:
            return 1
    else:
        print("\n[PASS] Planner Silo Invariant Verified: Zero illegal dependencies to orchestrator or viewer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
