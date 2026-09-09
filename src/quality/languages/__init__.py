"""
src/quality/languages/__init__.py

Language definitions, models, and detection tools for quality evaluation.
"""

from src.quality.languages.models import ALL_KNOWN_DIACRITICS, LanguageConfig
from src.quality.languages.definitions import (
    POLISH_CONFIG,
    GERMAN_CONFIG,
    FRENCH_CONFIG,
    SPANISH_CONFIG,
    ENGLISH_CONFIG,
    LANGUAGE_CONFIGS,
    get_language_config,
    register_language_config,
)
from src.quality.languages.detector import (
    LANGUAGE_DIACRITICS,
    LANGUAGE_STOPWORDS,
    detect_text_language,
    detect_page_language,
    detect_document_languages,
)

__all__ = [
    "ALL_KNOWN_DIACRITICS",
    "LanguageConfig",
    "POLISH_CONFIG",
    "GERMAN_CONFIG",
    "FRENCH_CONFIG",
    "SPANISH_CONFIG",
    "ENGLISH_CONFIG",
    "LANGUAGE_CONFIGS",
    "get_language_config",
    "register_language_config",
    "LANGUAGE_DIACRITICS",
    "LANGUAGE_STOPWORDS",
    "detect_text_language",
    "detect_page_language",
    "detect_document_languages",
]
