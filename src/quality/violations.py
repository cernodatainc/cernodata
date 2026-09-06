"""
src/quality/violations.py

Quality Violation Detector & Anomaly Extractor.
Generates structured violation records exported to quality_violations.json.
"""

import re
from typing import List, Dict, Any
from src.dom import DOMNode, DocumentDOM
from src.quality.garbage import compute_garbage_ratio


def _check_garbage_violations(node: DOMNode, raw_text: str, counter: int) -> List[Dict[str, Any]]:
    """Checks node raw text for non-printable control character spikes."""
    gb_ratio = compute_garbage_ratio(raw_text)
    if gb_ratio <= 0.05:
        return []
    return [{
        "violation_id": f"viol_p{node.global_page_index}_v{counter}",
        "global_page_index": node.global_page_index,
        "node_id": node.node_id,
        "rule_type": "garbage_character_ratio",
        "severity": "HIGH",
        "detected_snippet": raw_text[:60],
        "description": f"High ratio of non-printable or corrupt control characters ({round(gb_ratio, 3)})",
        "bounding_box": node.bounding_box.to_dict()
    }]


def _check_polish_diacritic_violations(node: DOMNode, raw_text: str, lang: str, counter: int) -> List[Dict[str, Any]]:
    """Checks Polish text nodes for raw OCR 'q' character substitutions (e.g. 'piqtku' vs 'piątku')."""
    if lang != "pl":
        return []

    violations = []
    q_matches = re.findall(r"\b\w*q\w*\b", raw_text, re.IGNORECASE)
    for match in q_matches:
        clean_match = match.strip(".,;:!?()[]\"'*")
        if clean_match.lower() not in {"sql", "query", "q1", "q2", "q3", "q4", "quality", "qr", "quick"}:
            suggested = clean_match.replace("q", "ą").replace("Q", "Ą")
            violations.append({
                "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
                "global_page_index": node.global_page_index,
                "node_id": node.node_id,
                "rule_type": "ocr_character_substitution",
                "severity": "WARNING",
                "detected_snippet": clean_match,
                "suggested_correction": suggested,
                "description": f"OCR 'q' character substitution anomaly detected ('{clean_match}' -> '{suggested}')",
                "bounding_box": node.bounding_box.to_dict()
            })
    return violations


def detect_quality_violations(dom: DocumentDOM, language: str = "en") -> List[Dict[str, Any]]:
    """
    Scans DocumentDOM nodes for specific quality violations and anomalies.
    Composes single-rule check functions.
    """
    violations = []
    lang = language.lower().strip()
    counter = 1

    for node in dom.nodes:
        raw_text = node.content.get("raw_text", "")
        gb_viols = _check_garbage_violations(node, raw_text, counter)
        counter += len(gb_viols)
        violations.extend(gb_viols)

        lang_viols = _check_polish_diacritic_violations(node, raw_text, lang, counter)
        counter += len(lang_viols)
        violations.extend(lang_viols)

    return violations
