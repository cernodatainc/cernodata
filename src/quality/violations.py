"""
src/quality/violations.py

Quality Violation Detector & Anomaly Extractor.
Generates structured violation records exported to quality_violations.json.
"""

from typing import List, Dict, Any, Optional
from src.dom import DOMNode, DocumentDOM
from src.quality.garbage import compute_garbage_ratio, compute_garbage_details
from src.quality.language_config import LanguageConfig, get_language_config


def _check_garbage_violations(node: DOMNode, raw_text: str, counter: int) -> List[Dict[str, Any]]:
    """Checks node raw text for OCR damage, punctuation soup, or corrupt characters."""
    from src.quality.evaluator import load_quality_config
    threshold = load_quality_config().get("garbage_threshold", 0.05)

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
        "rule_type": "garbage_character_ratio",
        "severity": "HIGH",
        "detected_snippet": raw_text[:60],
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
        violations.append({
            "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
            "global_page_index": node.global_page_index,
            "node_id": node.node_id,
            "rule_type": "ocr_character_substitution",
            "severity": "WARNING",
            "detected_snippet": match_snippet,
            "suggested_correction": suggested,
            "description": f"OCR '{anom_char}' character substitution anomaly detected ('{match_snippet}' -> '{suggested}')",
            "bounding_box": node.bounding_box.to_dict()
        })

    # 2. Conflicting foreign diacritics (e.g. 'ö' umlaut in Polish hinted context)
    for conf_char, match_snippet, suggested in config.find_diacritic_conflicts(raw_text):
        violations.append({
            "violation_id": f"viol_p{node.global_page_index}_v{counter + len(violations)}",
            "global_page_index": node.global_page_index,
            "node_id": node.node_id,
            "rule_type": "diacritic_conflict",
            "severity": "WARNING",
            "detected_snippet": match_snippet,
            "suggested_correction": suggested,
            "description": f"Diacritic conflict detected: '{conf_char}' is not valid in {config.name} ('{match_snippet}' -> '{suggested}')",
            "bounding_box": node.bounding_box.to_dict()
        })

    return violations


def _check_polish_diacritic_violations(node: DOMNode, raw_text: str, lang: str, counter: int) -> List[Dict[str, Any]]:
    """Backward compatibility wrapper for Polish diacritic violations."""
    if lang != "pl":
        return []
    config = get_language_config("pl")
    return _check_diacritic_violations(node, raw_text, config, counter)


def detect_quality_violations(dom: DocumentDOM, language: str = "en") -> List[Dict[str, Any]]:
    """
    Scans DocumentDOM nodes for specific quality violations and anomalies.
    Composes single-rule check functions with language configuration rules.
    """
    violations = []
    lang = language.lower().strip()
    is_auto = (lang == "auto")

    page_configs: Dict[int, Optional[LanguageConfig]] = {}
    if is_auto:
        from src.quality.language import detect_document_languages
        page_langs = detect_document_languages(dom)
        page_configs = {p: get_language_config(l) for p, l in page_langs.items()}
    else:
        fixed_config = get_language_config(lang)

    counter = 1

    for node in dom.nodes:
        raw_text = node.content.get("raw_text", "")
        gb_viols = _check_garbage_violations(node, raw_text, counter)
        counter += len(gb_viols)
        violations.extend(gb_viols)

        cfg = page_configs.get(node.global_page_index) if is_auto else fixed_config
        lang_viols = _check_diacritic_violations(node, raw_text, cfg, counter)
        counter += len(lang_viols)
        violations.extend(lang_viols)

    return violations
