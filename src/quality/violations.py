"""
src/quality/violations.py

Quality Violation Detector & Anomaly Extractor.
Generates structured violation records exported to quality_violations.json.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Sequence
from src.dom import DOMNode, DocumentDOM
from src.quality.garbage import compute_garbage_details
from src.quality.language_config import LanguageConfig, get_language_config
from src.quality.evaluator import load_quality_config
from src.quality.layers import VerificationLayer, normalize_layers

def _check_garbage_violations(
    node: DOMNode, raw_text: str, counter: int, threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Checks node raw text for OCR damage, punctuation soup, or corrupt characters."""
    if threshold is None:
        threshold = float(load_quality_config().get("garbage_threshold", 0.05))

    details = compute_garbage_details(raw_text)
    gb_ratio = details["ratio"]
    if gb_ratio <= threshold:
        return []

    reasons = []
    if details.get("unicode_ratio", 0) > 0:
        reasons.append("unicode corruption")
    if details.get("rep_ratio", 0) > 0:
        reasons.append("character repetition")
    if details.get("soup_ratio", 0) > 0:
        reasons.append("punctuation soup / fragmented OCR tokens")
    if details.get("low_alnum_penalty", 0) > 0:
        reasons.append("low alphanumeric ratio")

    desc_detail = f" ({', '.join(reasons)})" if reasons else ""
    return [{
        "violation_id": f"viol_p{node.global_page_index}_v{counter}",
        "global_page_index": node.global_page_index,
        "node_id": node.node_id,
        "type": "symbols",
        "rule_type": "garbage_character_ratio",
        "severity": "HIGH",
        "detected_snippet": raw_text[:60],
        "suggestion": None,
        "suppressed": False,
        "description": f"High ratio of OCR noise or corrupt characters ({round(gb_ratio, 3)}){desc_detail}",
        "bounding_box": node.bounding_box.to_dict()
    }]


def _check_diacritic_violations(
    node: DOMNode, raw_text: str, config: Optional[LanguageConfig], counter: int
) -> List[Dict[str, Any]]:
    """Checks text nodes for OCR substitution anomalies and conflicting diacritics."""
    if not config or not raw_text or config.code == "en":
        return []

    violations: List[Dict[str, Any]] = []

    # 1. OCR character substitution anomalies (e.g. 'q' -> 'ą' in Polish)
    for anom_char, match_snippet, suggested in config.find_anomalous_substitutions(raw_text):
        rewrite = raw_text.replace(match_snippet, suggested, 1) if match_snippet else raw_text
        violations.append({
            "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
            "global_page_index": node.global_page_index,
            "node_id": node.node_id,
            "type": "diacritic",
            "rule_type": "ocr_character_substitution",
            "severity": "WARNING",
            "detected_snippet": match_snippet,
            "suggested_correction": suggested,
            "suggestion": rewrite,
            "suppressed": False,
            "description": f"OCR '{anom_char}' character substitution anomaly detected ('{match_snippet}' -> '{suggested}')",
            "bounding_box": node.bounding_box.to_dict()
        })

    # 2. Conflicting foreign diacritics (e.g. 'ö' umlaut in Polish hinted context)
    for conf_char, match_snippet, suggested in config.find_diacritic_conflicts(raw_text):
        rewrite = raw_text.replace(match_snippet, suggested, 1) if match_snippet else raw_text
        violations.append({
            "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
            "global_page_index": node.global_page_index,
            "node_id": node.node_id,
            "type": "diacritic",
            "rule_type": "diacritic_conflict",
            "severity": "WARNING",
            "detected_snippet": match_snippet,
            "suggested_correction": suggested,
            "suggestion": rewrite,
            "suppressed": False,
            "description": f"Diacritic conflict detected: '{conf_char}' is not valid in {config.name} ('{match_snippet}' -> '{suggested}')",
            "bounding_box": node.bounding_box.to_dict()
        })

    return violations


def _check_structural_assertion_violations(
    dom: DocumentDOM, counter: int = 1
) -> List[Dict[str, Any]]:
    """Evaluates Level 3 structural and semantic layout consistency."""
    # TODO(TASK-102): Hook Level 3 structural & semantic spot-checks (`AssertionEvaluator`) here when a
    # `DocumentAssertionSuite` is provided (expected headers, regex patterns, forbidden boilerplate).
    violations: List[Dict[str, Any]] = []
    pages_nodes: Dict[int, List[DOMNode]] = {}
    for node in dom.nodes:
        pages_nodes.setdefault(node.global_page_index, []).append(node)

    for page_idx, p_nodes in pages_nodes.items():
        for idx, node in enumerate(p_nodes):
            raw_text = (node.content.get("raw_text") or "").strip()
            # 1. Empty structural text container
            if node.type in ("paragraph", "heading") and not raw_text:
                violations.append({
                    "violation_id": f"viol_p{page_idx}_v{counter + len(violations)}",
                    "global_page_index": page_idx,
                    "node_id": node.node_id,
                    "type": VerificationLayer.STRUCTURE.value,
                    "rule_type": "empty_structural_container",
                    "severity": "WARNING",
                    "detected_snippet": "",
                    "suggestion": None,
                    "suppressed": False,
                    "description": f"Empty structural {node.type} container without textual content",
                    "bounding_box": node.bounding_box.to_dict(),
                })
            # 2. Orphan heading (heading element is trailing node on page with no body text following)
            elif node.type == "heading" and idx == len(p_nodes) - 1 and len(p_nodes) > 1:
                violations.append({
                    "violation_id": f"viol_p{page_idx}_v{counter + len(violations)}",
                    "global_page_index": page_idx,
                    "node_id": node.node_id,
                    "type": VerificationLayer.STRUCTURE.value,
                    "rule_type": "orphan_heading",
                    "severity": "INFO",
                    "detected_snippet": raw_text[:60],
                    "suggestion": None,
                    "suppressed": False,
                    "description": "Orphan heading detected at page boundary with zero trailing content",
                    "bounding_box": node.bounding_box.to_dict(),
                })

    return violations


def _check_table_grid_violations(
    dom: DocumentDOM, counter: int = 1
) -> List[Dict[str, Any]]:
    """Evaluates Level 4 Markdown and tabular grid consistency."""
    # TODO(TASK-103): Replace static cell_alignment_score fallback with real Level 4 Markdown table
    # grid validation (column count consistency across rows, numeric alignment, and empty header checks).
    violations: List[Dict[str, Any]] = []
    for node in dom.nodes:
        if node.type != "table_grid":
            continue
        align_score = float(node.content.get("cell_alignment_score", 1.0))
        if align_score < 0.60:
            violations.append({
                "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
                "global_page_index": node.global_page_index,
                "node_id": node.node_id,
                "type": VerificationLayer.TABLES.value,
                "rule_type": "low_cell_alignment",
                "severity": "WARNING",
                "detected_snippet": str(node.content.get("raw_text", ""))[:60],
                "suggestion": None,
                "suppressed": False,
                "description": f"Table cell alignment score degraded ({round(align_score, 2)} < 0.60)",
                "bounding_box": node.bounding_box.to_dict(),
            })
        rows = node.content.get("rows")
        if isinstance(rows, list) and len(rows) > 1:
            row_lens = [len(r) for r in rows if isinstance(r, list)]
            if len(set(row_lens)) > 1:
                violations.append({
                    "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
                    "global_page_index": node.global_page_index,
                    "node_id": node.node_id,
                    "type": VerificationLayer.TABLES.value,
                    "rule_type": "table_column_count_mismatch",
                    "severity": "WARNING",
                    "detected_snippet": f"Column counts: {row_lens[:4]}",
                    "suggestion": None,
                    "suppressed": False,
                    "description": "Inconsistent column counts across table rows",
                    "bounding_box": node.bounding_box.to_dict(),
                })
    return violations


def _check_geometry_violations(
    dom: DocumentDOM, counter: int = 1
) -> List[Dict[str, Any]]:
    """Evaluates Level 5 spatial geometry and bounding box integrity."""
    # TODO(TASK-902): Hook validate_template_application to emit TEMPLATE_MISAPPLICATION violations.
    violations: List[Dict[str, Any]] = []
    for node in dom.nodes:
        bbox = node.bounding_box
        if bbox.x1 < bbox.x0 or bbox.y1 < bbox.y0:
            violations.append({
                "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
                "global_page_index": node.global_page_index,
                "node_id": node.node_id,
                "type": VerificationLayer.GEOMETRY.value,
                "rule_type": "inverted_bounding_box",
                "severity": "HIGH",
                "detected_snippet": str(node.content.get("raw_text", ""))[:60],
                "suggestion": None,
                "suppressed": False,
                "description": f"Inverted bounding box coordinates ({bbox.x0}, {bbox.y0}) -> ({bbox.x1}, {bbox.y1})",
                "bounding_box": bbox.to_dict(),
            })
        elif bbox.x0 < 0.0 or bbox.y0 < 0.0:
            violations.append({
                "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
                "global_page_index": node.global_page_index,
                "node_id": node.node_id,
                "type": VerificationLayer.GEOMETRY.value,
                "rule_type": "out_of_bounds_bounding_box",
                "severity": "WARNING",
                "detected_snippet": str(node.content.get("raw_text", ""))[:60],
                "suggestion": None,
                "suppressed": False,
                "description": f"Negative coordinate out-of-bounds bounding box ({bbox.x0}, {bbox.y0})",
                "bounding_box": bbox.to_dict(),
            })
        elif bbox.width <= 0.0 or bbox.height <= 0.0:
            violations.append({
                "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
                "global_page_index": node.global_page_index,
                "node_id": node.node_id,
                "type": VerificationLayer.GEOMETRY.value,
                "rule_type": "zero_area_bounding_box",
                "severity": "WARNING",
                "detected_snippet": str(node.content.get("raw_text", ""))[:60],
                "suggestion": None,
                "suppressed": False,
                "description": f"Degenerate zero-area bounding box ({bbox.width}x{bbox.height})",
                "bounding_box": bbox.to_dict(),
            })
    return violations


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
    active_layers = set(normalize_layers(layers))
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

    check_symbols = VerificationLayer.SYMBOLS.value in active_layers
    check_diacritics = VerificationLayer.DIACRITICS.value in active_layers

    for node in dom.nodes:
        existing_suppressed: Dict[str, bool] = {}
        for ev in getattr(node, "violations", []):
            if isinstance(ev, dict):
                supp_val = ev.get("suppressed", False)
                is_supp = (supp_val is True) or (str(supp_val).lower() in ("true", "1"))
                if ev.get("violation_id"):
                    existing_suppressed[ev["violation_id"]] = is_supp
                if ev.get("rule_type"):
                    existing_suppressed[ev["rule_type"]] = is_supp

        raw_text = node.content.get("raw_text", "")
        node_viols: List[Dict[str, Any]] = []

        if check_symbols:
            gb_viols = _check_garbage_violations(node, raw_text, counter, threshold=garbage_threshold)
            counter += len(gb_viols)
            node_viols.extend(gb_viols)

        if check_diacritics:
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

    if VerificationLayer.STRUCTURE.value in active_layers:
        struct_viols = _check_structural_assertion_violations(dom, counter=counter)
        counter += len(struct_viols)
        violations.extend(struct_viols)

    if VerificationLayer.TABLES.value in active_layers:
        table_viols = _check_table_grid_violations(dom, counter=counter)
        counter += len(table_viols)
        violations.extend(table_viols)

    if VerificationLayer.GEOMETRY.value in active_layers:
        geom_viols = _check_geometry_violations(dom, counter=counter)
        counter += len(geom_viols)
        violations.extend(geom_viols)

    violations.extend(_check_template_misapplication_violations(dom))
    violations.extend(_check_dataset_retrieval_violations(dom))
    return violations
