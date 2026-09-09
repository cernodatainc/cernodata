"""
src/quality/garbage.py

Garbage character ratio & non-printable character metrics.
Detects real-world OCR damage:
- Unicode anomalies: U+FFFD, control characters, private-use code points
- Character repetition: 4+ identical characters in a row
- Punctuation soup & unmatched brackets/parentheses
- Broken/isolated 1-2 character non-words and fragments
- Low alphanumeric ratio in punctuation-heavy sections
"""

from typing import Dict, Any
from src.quality.garbage_helpers import (
    ALLOWED_STANDALONE,
    VALID_SHORT_WORDS,
    evaluate_unicode_anomalies,
    evaluate_character_repetitions,
    evaluate_punctuation_soup_and_noise,
    compute_low_alnum_penalty,
)

__all__ = [
    "ALLOWED_STANDALONE",
    "VALID_SHORT_WORDS",
    "compute_garbage_details",
    "compute_garbage_ratio",
]


def compute_garbage_details(text: str) -> Dict[str, Any]:
    """
    Evaluates text for OCR damage signals and returns detailed signal breakdowns
    and composite ratio in range [0.0, 1.0].
    """
    if not text or not text.strip():
        return {
            "ratio": 0.0,
            "unicode_ratio": 0.0,
            "rep_ratio": 0.0,
            "soup_ratio": 0.0,
            "low_alnum_penalty": 0.0,
            "noise_tokens": []
        }

    clean_text = text.strip()
    total_len = len(clean_text)
    non_space_chars = [c for c in clean_text if not c.isspace()]
    if not non_space_chars:
        return {
            "ratio": 0.0,
            "unicode_ratio": 0.0,
            "rep_ratio": 0.0,
            "soup_ratio": 0.0,
            "low_alnum_penalty": 0.0,
            "noise_tokens": []
        }

    # 1. Unicode anomalies & control chars
    unicode_anom = evaluate_unicode_anomalies(clean_text)
    unicode_ratio = unicode_anom / total_len

    # 2. Character repetition (4+ identical characters in a row)
    rep_chars = evaluate_character_repetitions(clean_text)
    rep_ratio = rep_chars / total_len

    # 3. Punctuation soup, unmatched brackets, & fragmented OCR tokens
    tokens = clean_text.split()
    soup_chars, noise_tokens = evaluate_punctuation_soup_and_noise(clean_text, tokens)
    soup_ratio = soup_chars / total_len

    # 4. Low alphanumeric ratio penalty
    low_alnum_penalty = compute_low_alnum_penalty(non_space_chars)

    # Composite garbage ratio
    composite = min(
        1.0,
        (unicode_ratio * 1.5) +
        (rep_ratio * 1.0) +
        (soup_ratio * 0.9) +
        low_alnum_penalty
    )

    return {
        "ratio": round(composite, 4),
        "unicode_ratio": round(unicode_ratio, 4),
        "rep_ratio": round(rep_ratio, 4),
        "soup_ratio": round(soup_ratio, 4),
        "low_alnum_penalty": round(low_alnum_penalty, 4),
        "noise_tokens": noise_tokens
    }


def compute_garbage_ratio(text: str) -> float:
    """
    Measures ratio of non-printable, unicode corrupt, or fragmented OCR garbage.
    Returns float in range [0.0, 1.0].
    """
    details = compute_garbage_details(text)
    return details["ratio"]
