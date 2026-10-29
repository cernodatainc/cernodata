"""
src/quality/handlers_structural.py

Structural, tabular, and geometric verification layer handlers.
Implements Level 3 (Structure), Level 4 (Tables), and Level 5 (Geometry).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.dom import DOMNode, DocumentDOM
from src.quality.handlers import VerificationLayerHandler, make_node_violation
from src.quality.language_config import LanguageConfig
from src.quality.layers import VerificationLayer


class StructureLayerHandler(VerificationLayerHandler):
    """Level 3 verification: Structural and semantic layout consistency."""

    @property
    def layer_id(self) -> str:
        return VerificationLayer.STRUCTURE.value

    def detect_violations(
        self,
        dom: DocumentDOM,
        counter: int = 1,
        language: Optional[str] = "en",
        page_configs: Optional[Dict[int, Optional[LanguageConfig]]] = None,
        fixed_config: Optional[LanguageConfig] = None,
    ) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []
        pages_nodes: Dict[int, List[DOMNode]] = {}
        for node in dom.nodes:
            pages_nodes.setdefault(node.global_page_index, []).append(node)

        for _page_idx, p_nodes in pages_nodes.items():
            for idx, node in enumerate(p_nodes):
                raw_text = (node.content.get("raw_text") or "").strip()
                if node.type in ("paragraph", "heading") and not raw_text:
                    violations.append(
                        make_node_violation(
                            node=node,
                            counter=counter + len(violations),
                            v_type=VerificationLayer.STRUCTURE.value,
                            rule_type="empty_structural_container",
                            severity="WARNING",
                            description=f"Empty structural {node.type} container without textual content",
                        )
                    )
                elif node.type == "heading" and idx == len(p_nodes) - 1 and len(p_nodes) > 1:
                    violations.append(
                        make_node_violation(
                            node=node,
                            counter=counter + len(violations),
                            v_type=VerificationLayer.STRUCTURE.value,
                            rule_type="orphan_heading",
                            severity="INFO",
                            detected_snippet=raw_text[:60],
                            description="Orphan heading detected at page boundary with zero trailing content",
                        )
                    )
        return violations

    def evaluate_node(
        self,
        node: DOMNode,
        language: Optional[str] = "en",
        diacritic_hit: float = 0.20,
        config: Optional[LanguageConfig] = None,
        suppressed_types: Optional[Dict[str, bool]] = None,
        garbage_multiplier: float = 3.0,
    ) -> float:
        raw_text = (node.content.get("raw_text") or "").strip()
        if node.type in ("paragraph", "heading") and not raw_text:
            return 0.0
        return 1.0


class TablesLayerHandler(VerificationLayerHandler):
    """Level 4 verification: Table grid integrity and cell alignment consistency."""

    @property
    def layer_id(self) -> str:
        return VerificationLayer.TABLES.value

    def detect_violations(
        self,
        dom: DocumentDOM,
        counter: int = 1,
        language: Optional[str] = "en",
        page_configs: Optional[Dict[int, Optional[LanguageConfig]]] = None,
        fixed_config: Optional[LanguageConfig] = None,
    ) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []
        for node in dom.nodes:
            if node.type != "table_grid":
                continue
            align_score = float(node.content.get("cell_alignment_score", 1.0))
            if align_score < 0.60:
                violations.append(
                    make_node_violation(
                        node=node,
                        counter=counter + len(violations),
                        v_type=VerificationLayer.TABLES.value,
                        rule_type="low_cell_alignment",
                        severity="WARNING",
                        detected_snippet=str(node.content.get("raw_text", ""))[:60],
                        description=f"Table cell alignment score degraded ({round(align_score, 2)} < 0.60)",
                    )
                )
            rows = node.content.get("rows")
            if isinstance(rows, list) and len(rows) > 1:
                row_lens = [len(r) for r in rows if isinstance(r, list)]
                if len(set(row_lens)) > 1:
                    violations.append(
                        make_node_violation(
                            node=node,
                            counter=counter + len(violations),
                            v_type=VerificationLayer.TABLES.value,
                            rule_type="table_column_count_mismatch",
                            severity="WARNING",
                            detected_snippet=f"Column counts: {row_lens[:4]}",
                            description="Inconsistent column counts across table rows",
                        )
                    )
        return violations

    def evaluate_node(
        self,
        node: DOMNode,
        language: Optional[str] = "en",
        diacritic_hit: float = 0.20,
        config: Optional[LanguageConfig] = None,
        suppressed_types: Optional[Dict[str, bool]] = None,
        garbage_multiplier: float = 3.0,
    ) -> float:
        if node.type == "table_grid":
            return float(node.content.get("cell_alignment_score", 0.95))
        return 1.0


class GeometryLayerHandler(VerificationLayerHandler):
    """Level 5 verification: Spatial geometry, coordinate inversion, and zero-area bounding boxes."""

    @property
    def layer_id(self) -> str:
        return VerificationLayer.GEOMETRY.value

    def detect_violations(
        self,
        dom: DocumentDOM,
        counter: int = 1,
        language: Optional[str] = "en",
        page_configs: Optional[Dict[int, Optional[LanguageConfig]]] = None,
        fixed_config: Optional[LanguageConfig] = None,
    ) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []
        for node in dom.nodes:
            bbox = node.bounding_box
            snippet = str(node.content.get("raw_text", ""))[:60]
            if bbox.x1 < bbox.x0 or bbox.y1 < bbox.y0:
                violations.append(
                    make_node_violation(
                        node=node,
                        counter=counter + len(violations),
                        v_type=VerificationLayer.GEOMETRY.value,
                        rule_type="inverted_bounding_box",
                        severity="HIGH",
                        detected_snippet=snippet,
                        description=f"Inverted bounding box coordinates ({bbox.x0}, {bbox.y0}) -> ({bbox.x1}, {bbox.y1})",
                    )
                )
            elif bbox.x0 < 0.0 or bbox.y0 < 0.0:
                violations.append(
                    make_node_violation(
                        node=node,
                        counter=counter + len(violations),
                        v_type=VerificationLayer.GEOMETRY.value,
                        rule_type="out_of_bounds_bounding_box",
                        severity="WARNING",
                        detected_snippet=snippet,
                        description=f"Negative coordinate out-of-bounds bounding box ({bbox.x0}, {bbox.y0})",
                    )
                )
            elif bbox.width <= 0.0 or bbox.height <= 0.0:
                violations.append(
                    make_node_violation(
                        node=node,
                        counter=counter + len(violations),
                        v_type=VerificationLayer.GEOMETRY.value,
                        rule_type="zero_area_bounding_box",
                        severity="WARNING",
                        detected_snippet=snippet,
                        description=f"Degenerate zero-area bounding box ({bbox.width}x{bbox.height})",
                    )
                )
        return violations

    def evaluate_node(
        self,
        node: DOMNode,
        language: Optional[str] = "en",
        diacritic_hit: float = 0.20,
        config: Optional[LanguageConfig] = None,
        suppressed_types: Optional[Dict[str, bool]] = None,
        garbage_multiplier: float = 3.0,
    ) -> float:
        bbox = node.bounding_box
        if bbox.width <= 0.0 or bbox.height <= 0.0 or bbox.x1 < bbox.x0 or bbox.y1 < bbox.y0:
            return 0.0
        return 1.0


__all__ = [
    "GeometryLayerHandler",
    "StructureLayerHandler",
    "TablesLayerHandler",
]
