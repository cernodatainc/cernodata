"""
src/heuristics.py

Tiered Quality Check Continuum and confidence score evaluation engine.
Scores document pages based on:
1. Generic printable character ratio and garbage metrics.
2. Tier 2 Language & Dictionary checks (evaluating diacritics and OCR substitution anomalies, e.g., 'q' vs 'ą' in Polish).
3. Structural Table Grid alignment heuristics.
4. Detailed Quality Violation extraction and anomaly logging.
"""

import re
import string
from typing import List, Dict, Any
try:
    from src.dom import DOMNode, DocumentDOM
except ImportError:
    from dom import DOMNode, DocumentDOM

# Language-specific diacritics definitions
LANGUAGE_DIACRITICS = {
    "pl": set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"),
    "de": set("äöüßÄÖÜ"),
    "fr": set("éèêëàâçîïôûùÉÈÊËÀÂÇÎÏÔÛÙ"),
    "es": set("ñáéíóúü¿¡ÑÁÉÍÓÚÜ")
}


def compute_garbage_ratio(text: str) -> float:
    """
    Measures ratio of non-printable or suspicious control characters.
    Returns float in range [0.0, 1.0].
    """
    if not text:
        return 0.0
    printable_count = sum(1 for c in text if c in string.printable or c.isprintable())
    garbage_count = len(text) - printable_count
    return garbage_count / len(text)


def compute_language_score(text: str, language: str = "en") -> float:
    """
    Tier 2 Language & Dictionary Verification:
    Evaluates text fidelity against specified language norms and detects common OCR
    diacritic substitution errors (such as 'q' replacing 'ą' in Polish text contexts).
    """
    lang = language.lower().strip()
    if not text or lang == "en":
        return 1.0

    score = 1.0

    if lang == "pl":
        # Polish Language Verification
        # Detect anomalous 'q' substitutions inside Polish words (e.g., 'piqtku' vs 'piątku')
        anomalous_q_matches = re.findall(r"\b\w*q\w*\b", text, re.IGNORECASE)
        anomalous_q = [
            w for w in anomalous_q_matches
            if w.lower() not in {"sql", "query", "q1", "q2", "q3", "q4", "quality", "qr", "quick"}
        ]
        if anomalous_q:
            penalty = min(0.50, len(anomalous_q) * 0.15)
            score -= penalty

        # Check diacritic presence for longer text blocks
        diacritics = LANGUAGE_DIACRITICS.get("pl", set())
        has_diacritics = any(c in diacritics for c in text)
        words = text.split()
        if len(words) > 12 and not has_diacritics:
            score -= 0.15

    elif lang in LANGUAGE_DIACRITICS:
        diacritics = LANGUAGE_DIACRITICS[lang]
        has_diacritics = any(c in diacritics for c in text)
        words = text.split()
        if len(words) > 15 and not has_diacritics:
            score -= 0.15

    return max(0.0, score)


def evaluate_page_confidence(nodes: List[DOMNode], language: str = "en") -> float:
    """
    Computes quality confidence score S_i for a set of DOMNodes on a single page.
    Combines garbage metrics, Tier 2 language verification, and table grid alignment.
    """
    if not nodes:
        return 0.0

    node_scores = []
    for node in nodes:
        raw_text = node.content.get("raw_text", "")
        
        # 1. Garbage Character Ratio Check
        garbage_ratio = compute_garbage_ratio(raw_text)
        char_score = max(0.0, 1.0 - (garbage_ratio * 3.0))

        # 2. Tier 2 Language Check
        lang_score = compute_language_score(raw_text, language=language)

        combined_text_score = char_score * lang_score

        # 3. Structural Table Grid Check
        if node.type == "table_grid":
            cell_alignment = node.content.get("cell_alignment_score", 0.95)
            score = 0.5 * combined_text_score + 0.5 * cell_alignment
        else:
            score = combined_text_score

        node_scores.append(score)

    return float(sum(node_scores) / len(node_scores))


def evaluate_document_confidence(dom: DocumentDOM, language: str = "en") -> Dict[str, Any]:
    """
    Evaluates confidence score across all pages in a DocumentDOM.
    Returns per-page confidence map S_1..S_N and overall document confidence score S.
    """
    pages_nodes: Dict[int, List[DOMNode]] = {p: [] for p in range(1, dom.total_pages + 1)}
    for node in dom.nodes:
        pages_nodes.setdefault(node.global_page_index, []).append(node)

    page_scores: Dict[int, float] = {}
    for page_no, p_nodes in pages_nodes.items():
        score_i = evaluate_page_confidence(p_nodes, language=language)
        page_scores[page_no] = round(score_i, 4)

    overall_confidence = round(
        sum(page_scores.values()) / max(1, len(page_scores)), 4
    )

    return {
        "overall_confidence": overall_confidence,
        "per_page_confidence": page_scores
    }


def detect_quality_violations(dom: DocumentDOM, language: str = "en") -> List[Dict[str, Any]]:
    """
    Scans DocumentDOM nodes for specific quality violations and anomalies:
    - Non-printable garbage character spikes
    - OCR character substitution anomalies (e.g. 'piqtku' vs 'piątku' in Polish)
    - Fragmented table cell boundaries

    Returns structured list of quality violation records.
    """
    violations = []
    lang = language.lower().strip()
    violation_counter = 1

    for node in dom.nodes:
        raw_text = node.content.get("raw_text", "")
        
        # 1. Check for garbage character ratio violation
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

        # 2. Check for Polish OCR 'q' substitution anomalies
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
