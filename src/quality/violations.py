"""
src/quality/violations.py

Quality Violation Detector & Anomaly Extractor.
Generates structured violation records exported to quality_violations.json.
"""

import re
from typing import List, Dict, Any
from src.dom import DocumentDOM
from src.quality.garbage import compute_garbage_ratio


def detect_quality_violations(dom: DocumentDOM, language: str = "en") -> List[Dict[str, Any]]:
    """
    Scans DocumentDOM nodes for specific quality violations and anomalies.
    """
    violations = []
    lang = language.lower().strip()
    violation_counter = 1

    for node in dom.nodes:
        raw_text = node.content.get("raw_text", "")
        
        # 1. Garbage character ratio violation
        gb_ratio = compute_garbage_ratio(raw_text)
        if gb_ratio > 0.05:
            violations.append({
                "violation_id": f"viol_p{node.global_page_index}_v{violation_counter}",
                "global_page_index": node.global_page_index,
                "node_id": node.node_id,
                "rule_type": "garbage_character_ratio",
                "severity": "HIGH",
                "detected_snippet": raw_text[:60],
                "description": f"High ratio of non-printable or corrupt control characters ({round(gb_ratio, 3)})",
                "bounding_box": node.bounding_box.to_dict()
            })
            violation_counter += 1

        # 2. Polish OCR 'q' substitution anomalies
        if lang == "pl":
            q_matches = re.findall(r"\b\w*q\w*\b", raw_text, re.IGNORECASE)
            for match in q_matches:
                clean_match = match.strip(".,;:!?()[]\"'*")
                if clean_match.lower() not in {"sql", "query", "q1", "q2", "q3", "q4", "quality", "qr", "quick"}:
                    suggested = clean_match.replace("q", "ą").replace("Q", "Ą")
                    violations.append({
                        "violation_id": f"viol_p{node.global_page_index}_v{violation_counter}",
                        "global_page_index": node.global_page_index,
                        "node_id": node.node_id,
                        "rule_type": "ocr_character_substitution",
                        "severity": "WARNING",
                        "detected_snippet": clean_match,
                        "suggested_correction": suggested,
                        "description": f"OCR 'q' character substitution anomaly detected ('{clean_match}' -> '{suggested}')",
                        "bounding_box": node.bounding_box.to_dict()
                    })
                    violation_counter += 1

    return violations
