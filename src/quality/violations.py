"""
src/quality/violations.py

Quality Violation Detector & Anomaly Extractor.
Generates structured violation records exported to quality_violations.json.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Sequence
from src.dom import DOMNode, DocumentDOM
from src.quality.evaluator import load_quality_config
from src.quality.handlers import (
    DiacriticsLayerHandler,
    GeometryLayerHandler,
    StructureLayerHandler,
    SymbolsLayerHandler,
    TablesLayerHandler,
    get_suppressed_violation_lookup,
)
from src.quality.language_config import LanguageConfig, get_language_config
from src.quality.layers import ActiveVerificationLayers


def _check_garbage_violations(
    node: DOMNode, raw_text: str, counter: int, threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Checks node raw text for OCR damage, punctuation soup, or corrupt characters."""
    if threshold is None:
        threshold = float(load_quality_config().get("garbage_threshold", 0.05))
    return SymbolsLayerHandler.check_node_violations(node, raw_text, counter, threshold=threshold)


def _check_diacritic_violations(
    node: DOMNode, raw_text: str, config: Optional[LanguageConfig], counter: int
) -> List[Dict[str, Any]]:
    """Checks text nodes for OCR substitution anomalies and conflicting diacritics."""
    return DiacriticsLayerHandler.check_node_violations(node, raw_text, config, counter)


def _check_structural_assertion_violations(
    dom: DocumentDOM, counter: int = 1
) -> List[Dict[str, Any]]:
    """Evaluates Level 3 structural and semantic layout consistency."""
    # TODO(TASK-102): Hook Level 3 structural & semantic spot-checks (`AssertionEvaluator`) here when a
    # `DocumentAssertionSuite` is provided (expected headers, regex patterns, forbidden boilerplate).
    return StructureLayerHandler().detect_violations(dom, counter=counter)


def _check_table_grid_violations(
    dom: DocumentDOM, counter: int = 1
) -> List[Dict[str, Any]]:
    """Evaluates Level 4 Markdown and tabular grid consistency."""
    # TODO(TASK-103): Replace static cell_alignment_score fallback with real Level 4 Markdown table
    # grid validation (column count consistency across rows, numeric alignment, and empty header checks).
    return TablesLayerHandler().detect_violations(dom, counter=counter)


def _check_geometry_violations(
    dom: DocumentDOM, counter: int = 1
) -> List[Dict[str, Any]]:
    """Evaluates Level 5 spatial geometry and bounding box integrity."""
    # TODO(TASK-902): Hook validate_template_application to emit TEMPLATE_MISAPPLICATION violations.
    return GeometryLayerHandler().detect_violations(dom, counter=counter)


def _check_template_misapplication_violations(dom: DocumentDOM) -> List[Dict[str, Any]]:
    """No-op hook for detecting misapplied spatial document templates."""
    # TODO(TASK-902): Hook `validate_template_application` to emit `TEMPLATE_MISAPPLICATION` violations when
    # a user-supplied spatial template yields excessive empty or colliding zones.
    _ = dom
    return []


def _check_dataset_retrieval_violations(dom: DocumentDOM) -> List[Dict[str, Any]]:
    """No-op hook for Level 5 downstream RAG retrieval recall evaluation."""
    # TODO(TASK-106): Hook Level 5 downstream retrieval evaluation (`evaluate_retrieval_suite`) for batch runs.
    _ = dom
    return []


def detect_quality_violations(
    dom: DocumentDOM,
    language: Optional[str] = "en",
    page_languages: Optional[Dict[int, str]] = None,
    layers: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Scans DocumentDOM nodes for specific quality violations across selected verification layers.
    Composes single-rule check functions with language configuration and layer filters.
    Populates violations directly on each DOMNode.
    """
    violations: List[Dict[str, Any]] = []
    active_layers = ActiveVerificationLayers.from_layers(layers)
    lang = language.lower().strip() if language else "en"
    is_auto = (lang == "auto")

    page_configs: Dict[int, Optional[LanguageConfig]] = {}
    if is_auto:
        if page_languages is not None:
            page_langs = page_languages
        else:
            from src.quality.language import detect_document_languages
            page_langs = detect_document_languages(dom)
        page_configs = {p: get_language_config(lang_code) for p, lang_code in page_langs.items()}
    else:
        fixed_config = get_language_config(lang)

    garbage_threshold = float(load_quality_config().get("garbage_threshold", 0.05))
    counter = 1

    for node in dom.nodes:
        existing_suppressed = get_suppressed_violation_lookup(node)
        raw_text = node.content.get("raw_text", "")
        node_viols: List[Dict[str, Any]] = []

        if active_layers.symbols:
            gb_viols = _check_garbage_violations(node, raw_text, counter, threshold=garbage_threshold)
            counter += len(gb_viols)
            node_viols.extend(gb_viols)

        if active_layers.diacritics:
            cfg = page_configs.get(node.global_page_index) if is_auto else fixed_config
            lang_viols = _check_diacritic_violations(node, raw_text, cfg, counter)
            counter += len(lang_viols)
            node_viols.extend(lang_viols)

        for v in node_viols:
            v_id = v.get("violation_id", "")
            r_type = v.get("rule_type", "")
            if v_id in existing_suppressed:
                v["suppressed"] = existing_suppressed[v_id]
            elif r_type in existing_suppressed:
                v["suppressed"] = existing_suppressed[r_type]

        node.violations = node_viols
        violations.extend(node_viols)

    if active_layers.structure:
        struct_viols = _check_structural_assertion_violations(dom, counter=counter)
        counter += len(struct_viols)
        violations.extend(struct_viols)

    if active_layers.tables:
        table_viols = _check_table_grid_violations(dom, counter=counter)
        counter += len(table_viols)
        violations.extend(table_viols)

    if active_layers.geometry:
        geom_viols = _check_geometry_violations(dom, counter=counter)
        counter += len(geom_viols)
        violations.extend(geom_viols)

    violations.extend(_check_template_misapplication_violations(dom))
    violations.extend(_check_dataset_retrieval_violations(dom))
    return violations
