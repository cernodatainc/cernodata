"""
src/quality/language.py

Tier 2 Language & Dictionary Verification rules and diacritic anomaly metrics.
"""

from typing import Optional, Dict, Tuple, List
from src.dom import DOMNode, DocumentDOM
from src.quality.languages import (
    LanguageConfig,
    LANGUAGE_CONFIGS,
    ALL_KNOWN_DIACRITICS,
    LANGUAGE_DIACRITICS,
    LANGUAGE_STOPWORDS,
    get_language_config,
    register_language_config,
    detect_text_language,
    detect_page_language,
    detect_document_languages,
)

__all__ = [
    "LanguageConfig",
    "LANGUAGE_CONFIGS",
    "ALL_KNOWN_DIACRITICS",
    "LANGUAGE_DIACRITICS",
    "LANGUAGE_STOPWORDS",
    "get_language_config",
    "register_language_config",
    "detect_text_language",
    "detect_page_language",
    "detect_document_languages",
    "compute_language_score",
]


def compute_language_score(
    text: str, language: str = "en", diacritic_hit: Optional[float] = None
) -> float:
    """
    Tier 2 Language & Dictionary Verification:
    Evaluates text fidelity against specified language norms, detecting common OCR
    diacritic substitution errors and foreign diacritic conflicts.
    """
    lang = language.lower().strip()
    if not text or lang == "en":
        return 1.0

    config = get_language_config(lang)
    if config:
        return config.compute_score(text, diacritic_hit=diacritic_hit)

    return 1.0
