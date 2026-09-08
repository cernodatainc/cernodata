"""
src/quality/language.py

Tier 2 Language & Dictionary Verification rules and diacritic anomaly metrics.
"""

from src.quality.language_config import (
    LanguageConfig,
    LANGUAGE_CONFIGS,
    get_language_config,
    register_language_config
)

LANGUAGE_DIACRITICS = {
    code: cfg.valid_diacritics
    for code, cfg in LANGUAGE_CONFIGS.items()
    if cfg.valid_diacritics
}


from typing import Optional


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
