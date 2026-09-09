"""
src/quality/languages/detector.py

Language detection and stopword frequency heuristics across texts, pages, and DocumentDOM.
Loads stopwords from stopwords.json.
"""

import os
import json
import re
from typing import Dict, List, Tuple, Set
from src.dom import DOMNode, DocumentDOM
from src.quality.languages.models import ALL_KNOWN_DIACRITICS
from src.quality.languages.definitions import LANGUAGE_CONFIGS

_STOPWORDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stopwords.json")


def _load_stopwords() -> Dict[str, Set[str]]:
    # Extract stopwords from unified language configurations
    stopwords = {
        code: cfg.stopwords
        for code, cfg in LANGUAGE_CONFIGS.items()
        if cfg.stopwords
    }
    if stopwords:
        return stopwords

    if os.path.isfile(_STOPWORDS_PATH):
        with open(_STOPWORDS_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {code: set(words) for code, words in raw.items()}

    return {}


LANGUAGE_STOPWORDS: Dict[str, Set[str]] = _load_stopwords()

LANGUAGE_DIACRITICS: Dict[str, Set[str]] = {
    code: cfg.valid_diacritics
    for code, cfg in LANGUAGE_CONFIGS.items()
    if cfg.valid_diacritics
}


def detect_text_language(text: str) -> Tuple[str, float, Dict[str, float]]:
    """
    Auto-detects the probable language (en, pl, de, fr, es) for a text passage.
    Returns: (detected_code, confidence_score, scores_dict).
    """
    if not text or not text.strip():
        return "en", 1.0, {"en": 1.0, "pl": 0.0, "de": 0.0, "fr": 0.0, "es": 0.0}

    tokens = re.findall(r"\b\w+\b", text.lower())
    scores: Dict[str, float] = {code: 0.0 for code in ("pl", "de", "fr", "es", "en")}

    for char in text:
        if char in ALL_KNOWN_DIACRITICS:
            scores["en"] -= 4.0
            for code, diacritics in LANGUAGE_DIACRITICS.items():
                if char in diacritics:
                    scores[code] += 3.0
                else:
                    scores[code] -= 1.5

    for token in tokens:
        for code, stopwords in LANGUAGE_STOPWORDS.items():
            if token in stopwords:
                scores[code] += 2.0

    # Ensure scores are non-negative
    for code in scores:
        scores[code] = max(0.0, scores[code])

    total_score = sum(scores.values())
    if total_score <= 0.0:
        return "en", 1.0, {c: (1.0 if c == "en" else 0.0) for c in scores}

    # Normalize scores
    norm_scores = {code: round(score / total_score, 4) for code, score in scores.items()}
    best_lang = max(norm_scores, key=lambda k: norm_scores[k])
    confidence = norm_scores[best_lang]

    return best_lang, confidence, norm_scores


def detect_page_language(nodes: List[DOMNode]) -> Tuple[str, float, Dict[str, float]]:
    """Auto-detects the dominant language across all nodes on a specific page."""
    combined_text = " ".join(
        node.content.get("raw_text", "")
        for node in nodes
        if node.content and node.content.get("raw_text")
    )
    return detect_text_language(combined_text)


def detect_document_languages(dom: DocumentDOM) -> Dict[int, str]:
    """Maps each page number in a DocumentDOM to its detected language code."""
    pages_nodes: Dict[int, List[DOMNode]] = {p: [] for p in range(1, dom.total_pages + 1)}
    for node in dom.nodes:
        pages_nodes.setdefault(node.global_page_index, []).append(node)

    page_languages: Dict[int, str] = {}
    for page_no, nodes in pages_nodes.items():
        lang, _, _ = detect_page_language(nodes)
        page_languages[page_no] = lang

    return page_languages
