"""
src/quality/violations.py

Quality Violation Detector & Anomaly Extractor.
Generates structured violation records exported to quality_violations.json.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from src.dom import DOMNode, DocumentDOM
from src.quality.garbage import compute_garbage_details
from src.quality.language_config import LanguageConfig, get_language_config
from src.quality.evaluator import load_quality_config

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


def _check_structural_assertion_violations(dom: DocumentDOM) -> List[Dict[str, Any]]:
    """No-op hook for Level 3 single-document structural and semantic assertions."""
    # TODO(TASK-102): Hook Level 3 structural & semantic spot-checks (`AssertionEvaluator`) here when a
    # `DocumentAssertionSuite` is provided (expected headers, regex patterns, forbidden boilerplate).
    _ = dom
    return []


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


def detect_quality_violations(dom: DocumentDOM, language: Optional[str] = "en") -> List[Dict[str, Any]]:
    """
    Scans DocumentDOM nodes for specific quality violations and anomalies.
    Composes single-rule check functions with language configuration rules.
    Populates violations directly on each DOMNode.
    """
    violations = []
    lang = language.lower().strip() if language else "en"
    is_auto = (lang == "auto")

    page_configs: Dict[int, Optional[LanguageConfig]] = {}
    if is_auto:
        from src.quality.language import detect_document_languages
        page_langs = detect_document_languages(dom)
        page_configs = {p: get_language_config(lang_code) for p, lang_code in page_langs.items()}
    else:
        fixed_config = get_language_config(lang)

    garbage_threshold = float(load_quality_config().get("garbage_threshold", 0.05))
    counter = 1

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
        gb_viols = _check_garbage_violations(node, raw_text, counter, threshold=garbage_threshold)
        counter += len(gb_viols)

        cfg = page_configs.get(node.global_page_index) if is_auto else fixed_config
        lang_viols = _check_diacritic_violations(node, raw_text, cfg, counter)
        counter += len(lang_viols)

        node_viols = gb_viols + lang_viols
        for v in node_viols:
            v_id = v.get("violation_id", "")
            r_type = v.get("rule_type", "")
            if v_id in existing_suppressed:
                v["suppressed"] = existing_suppressed[v_id]
            elif r_type in existing_suppressed:
                v["suppressed"] = existing_suppressed[r_type]

        node.violations = node_viols
        violations.extend(node_viols)

    violations.extend(_check_structural_assertion_violations(dom))
    violations.extend(_check_template_misapplication_violations(dom))
    violations.extend(_check_dataset_retrieval_violations(dom))
    return violations
